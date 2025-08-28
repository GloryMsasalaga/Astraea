from celery import shared_task
from django.utils import timezone
from .models import (
    ReconciliationSession, 
    LedgerRecord, 
    BankRecord, 
    TransactionMatch, 
    ReconciliationException
)
import pandas as pd
import logging
from decimal import Decimal
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def process_reconciliation_files(self, session_id):
    """Process uploaded reconciliation files (CSV/Excel)"""
    
    try:
        session = ReconciliationSession.objects.get(id=session_id)
        session.status = 'processing'
        session.save()
        
        # Process ledger file
        ledger_records = process_ledger_file(session)
        session.total_ledger_records = len(ledger_records)
        
        # Process bank statement file
        bank_records = process_bank_statement_file(session)
        session.total_bank_records = len(bank_records)
        
        session.save()
        
        logger.info(f"File processing completed for session {session_id}. "
                   f"Ledger: {len(ledger_records)}, Bank: {len(bank_records)}")
        
        return {
            "status": "success", 
            "session_id": str(session_id),
            "ledger_records": len(ledger_records),
            "bank_records": len(bank_records)
        }
        
    except ReconciliationSession.DoesNotExist:
        logger.error(f"Reconciliation session {session_id} not found")
        return {"status": "error", "message": "Session not found"}
    
    except Exception as e:
        logger.error(f"File processing failed for session {session_id}: {str(e)}")
        
        if 'session' in locals():
            session.status = 'failed'
            session.save()
        
        return {"status": "error", "message": str(e)}


@shared_task(bind=True)
def start_reconciliation_matching(self, session_id):
    """Start the reconciliation matching process"""
    
    try:
        session = ReconciliationSession.objects.get(id=session_id)
        
        if session.status != 'processing':
            session.status = 'processing'
            session.save()
        
        # Get unmatched records
        ledger_records = session.ledger_records.filter(is_matched=False)
        bank_records = session.bank_records.filter(is_matched=False)
        
        logger.info(f"Starting reconciliation for session {session_id}. "
                   f"Ledger: {ledger_records.count()}, Bank: {bank_records.count()}")
        
        # Perform matching
        matches = perform_transaction_matching(session, ledger_records, bank_records)
        
        # Create exception records for unmatched items
        create_exception_records(session)
        
        # Update session statistics
        update_session_statistics(session)
        
        session.status = 'completed'
        session.processed_at = timezone.now()
        session.save()
        
        logger.info(f"Reconciliation completed for session {session_id}. "
                   f"Matches found: {len(matches)}")
        
        return {
            "status": "success", 
            "session_id": str(session_id),
            "matches_found": len(matches)
        }
        
    except ReconciliationSession.DoesNotExist:
        logger.error(f"Reconciliation session {session_id} not found")
        return {"status": "error", "message": "Session not found"}
    
    except Exception as e:
        logger.error(f"Reconciliation failed for session {session_id}: {str(e)}")
        
        if 'session' in locals():
            session.status = 'failed'
            session.save()
        
        return {"status": "error", "message": str(e)}


def process_ledger_file(session):
    """Process ledger file and create LedgerRecord objects"""
    
    file_path = session.ledger_file.path
    
    # Determine file type and read accordingly
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    else:  # Excel file
        df = pd.read_excel(file_path)
    
    # Clean and standardize column names
    df.columns = df.columns.str.strip().str.lower()
    
    # Map common column names to standard fields
    column_mapping = {
        'date': ['date', 'transaction_date', 'trans_date', 'posting_date'],
        'description': ['description', 'desc', 'transaction_description', 'details', 'memo'],
        'amount': ['amount', 'transaction_amount', 'debit', 'credit', 'value'],
        'reference': ['reference', 'ref', 'transaction_id', 'transaction_ref', 'check_number'],
        'account': ['account', 'account_number', 'account_name'],
        'category': ['category', 'type', 'transaction_type', 'class']
    }
    
    # Find the best matching columns
    mapped_columns = {}
    for field, possible_names in column_mapping.items():
        for col_name in possible_names:
            if col_name in df.columns:
                mapped_columns[field] = col_name
                break
    
    records = []
    for index, row in df.iterrows():
        try:
            # Extract and clean data
            date_value = parse_date(row.get(mapped_columns.get('date', 'date'), ''))
            amount_value = parse_amount(row.get(mapped_columns.get('amount', 'amount'), 0))
            description_value = str(row.get(mapped_columns.get('description', 'description'), '')).strip()
            
            if date_value and amount_value != 0 and description_value:
                record = LedgerRecord(
                    session=session,
                    date=date_value,
                    description=description_value,
                    amount=amount_value,
                    reference=str(row.get(mapped_columns.get('reference', ''), '')).strip(),
                    account=str(row.get(mapped_columns.get('account', ''), '')).strip(),
                    category=str(row.get(mapped_columns.get('category', ''), '')).strip(),
                    raw_data=row.to_dict(),
                    row_number=index + 1
                )
                records.append(record)
        
        except Exception as e:
            logger.warning(f"Skipping ledger row {index + 1}: {str(e)}")
            continue
    
    # Bulk create records
    if records:
        LedgerRecord.objects.bulk_create(records)
    
    return records


def process_bank_statement_file(session):
    """Process bank statement file and create BankRecord objects"""
    
    file_path = session.bank_statement_file.path
    
    # Determine file type and read accordingly
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    else:  # Excel file
        df = pd.read_excel(file_path)
    
    # Clean and standardize column names
    df.columns = df.columns.str.strip().str.lower()
    
    # Map common column names to standard fields
    column_mapping = {
        'date': ['date', 'transaction_date', 'posting_date', 'effective_date'],
        'description': ['description', 'transaction_description', 'details', 'memo', 'payee'],
        'amount': ['amount', 'transaction_amount', 'debit', 'credit'],
        'reference': ['reference', 'confirmation_number', 'transaction_id'],
        'balance': ['balance', 'running_balance', 'account_balance']
    }
    
    # Find the best matching columns
    mapped_columns = {}
    for field, possible_names in column_mapping.items():
        for col_name in possible_names:
            if col_name in df.columns:
                mapped_columns[field] = col_name
                break
    
    records = []
    for index, row in df.iterrows():
        try:
            # Extract and clean data
            date_value = parse_date(row.get(mapped_columns.get('date', 'date'), ''))
            amount_value = parse_amount(row.get(mapped_columns.get('amount', 'amount'), 0))
            description_value = str(row.get(mapped_columns.get('description', 'description'), '')).strip()
            
            if date_value and amount_value != 0 and description_value:
                balance_value = parse_amount(row.get(mapped_columns.get('balance', ''), None))
                
                record = BankRecord(
                    session=session,
                    date=date_value,
                    description=description_value,
                    amount=amount_value,
                    reference=str(row.get(mapped_columns.get('reference', ''), '')).strip(),
                    balance=balance_value,
                    raw_data=row.to_dict(),
                    row_number=index + 1
                )
                records.append(record)
        
        except Exception as e:
            logger.warning(f"Skipping bank row {index + 1}: {str(e)}")
            continue
    
    # Bulk create records
    if records:
        BankRecord.objects.bulk_create(records)
    
    return records


def perform_transaction_matching(session, ledger_records, bank_records):
    """Perform transaction matching between ledger and bank records"""
    
    matches = []
    date_tolerance = timedelta(days=session.date_tolerance_days)
    amount_tolerance = session.amount_tolerance
    
    for ledger_record in ledger_records:
        best_match = None
        best_score = 0.0
        
        for bank_record in bank_records.filter(is_matched=False):
            # Calculate match score
            score = calculate_match_score(
                ledger_record, 
                bank_record, 
                date_tolerance, 
                amount_tolerance
            )
            
            if score > best_score and score >= 0.7:  # Minimum confidence threshold
                best_score = score
                best_match = bank_record
        
        # Create match if found
        if best_match:
            # Calculate differences
            date_diff = abs((ledger_record.date - best_match.date).days)
            amount_diff = abs(ledger_record.amount - best_match.amount)
            
            # Determine match type
            if score >= 0.95:
                match_type = 'exact'
            elif score >= 0.8:
                match_type = 'partial'
            else:
                match_type = 'partial'
            
            match = TransactionMatch.objects.create(
                session=session,
                ledger_record=ledger_record,
                bank_record=best_match,
                match_type=match_type,
                confidence_score=best_score,
                date_difference_days=date_diff,
                amount_difference=amount_diff
            )
            
            # Mark records as matched
            ledger_record.is_matched = True
            ledger_record.match_confidence = best_score
            ledger_record.save()
            
            best_match.is_matched = True
            best_match.match_confidence = best_score
            best_match.save()
            
            matches.append(match)
    
    return matches


def calculate_match_score(ledger_record, bank_record, date_tolerance, amount_tolerance):
    """Calculate match score between two records"""
    
    score = 0.0
    
    # Date matching (30% weight)
    date_diff = abs((ledger_record.date - bank_record.date).days)
    if date_diff == 0:
        score += 0.3
    elif date_diff <= date_tolerance.days:
        score += 0.3 * (1 - date_diff / (date_tolerance.days + 1))
    
    # Amount matching (40% weight)
    amount_diff = abs(ledger_record.amount - bank_record.amount)
    if amount_diff == 0:
        score += 0.4
    elif amount_diff <= amount_tolerance:
        score += 0.4 * (1 - float(amount_diff) / (float(amount_tolerance) + 0.01))
    
    # Description similarity (30% weight)
    desc_score = calculate_description_similarity(
        ledger_record.description, 
        bank_record.description
    )
    score += 0.3 * desc_score
    
    return min(score, 1.0)


def calculate_description_similarity(desc1, desc2):
    """Calculate similarity between two descriptions"""
    
    # Clean and normalize descriptions
    desc1_clean = re.sub(r'[^\w\s]', '', desc1.lower()).strip()
    desc2_clean = re.sub(r'[^\w\s]', '', desc2.lower()).strip()
    
    # Split into words
    words1 = set(desc1_clean.split())
    words2 = set(desc2_clean.split())
    
    if not words1 or not words2:
        return 0.0
    
    # Calculate Jaccard similarity
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    if union == 0:
        return 0.0
    
    return intersection / union


def create_exception_records(session):
    """Create exception records for unmatched transactions"""
    
    # Unmatched ledger records
    unmatched_ledger = session.ledger_records.filter(is_matched=False)
    for record in unmatched_ledger:
        ReconciliationException.objects.create(
            session=session,
            exception_type='unmatched_ledger',
            ledger_record=record,
            description=f"Unmatched ledger transaction: {record.description[:100]}",
            severity='medium'
        )
    
    # Unmatched bank records
    unmatched_bank = session.bank_records.filter(is_matched=False)
    for record in unmatched_bank:
        ReconciliationException.objects.create(
            session=session,
            exception_type='unmatched_bank',
            bank_record=record,
            description=f"Unmatched bank transaction: {record.description[:100]}",
            severity='medium'
        )


def update_session_statistics(session):
    """Update session statistics after reconciliation"""
    
    session.matched_records = session.matches.count()
    session.unmatched_ledger_records = session.ledger_records.filter(is_matched=False).count()
    session.unmatched_bank_records = session.bank_records.filter(is_matched=False).count()
    session.save()


def parse_date(date_str):
    """Parse date from various formats"""
    
    if pd.isna(date_str) or not date_str:
        return None
    
    if isinstance(date_str, (datetime, pd.Timestamp)):
        return date_str.date()
    
    date_str = str(date_str).strip()
    
    # Common date formats
    formats = [
        '%Y-%m-%d',
        '%m/%d/%Y',
        '%d/%m/%Y',
        '%m-%d-%Y',
        '%d-%m-%Y',
        '%Y/%m/%d',
        '%B %d, %Y',
        '%b %d, %Y',
        '%d %B %Y',
        '%d %b %Y'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    # Try pandas date parser as fallback
    try:
        return pd.to_datetime(date_str).date()
    except:
        return None


def parse_amount(amount_str):
    """Parse amount from various formats"""
    
    if pd.isna(amount_str) or amount_str == '':
        return Decimal('0.00')
    
    if isinstance(amount_str, (int, float, Decimal)):
        return Decimal(str(amount_str))
    
    amount_str = str(amount_str).strip()
    
    # Remove common currency symbols and formatting
    amount_str = re.sub(r'[$£€¥,\s]', '', amount_str)
    
    # Handle parentheses for negative amounts
    if amount_str.startswith('(') and amount_str.endswith(')'):
        amount_str = '-' + amount_str[1:-1]
    
    try:
        return Decimal(amount_str)
    except:
        return Decimal('0.00')
