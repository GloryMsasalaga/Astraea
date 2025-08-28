# Auditing and Accounting Assistant System

A comprehensive Django-based auditing and accounting assistant system with document processing, reconciliation, and financial analytics capabilities.

## Features

### 🗂️ Document Analyzer Module
- Upload invoices, receipts, and contracts (PDF, JPG, PNG)
- OCR processing with Tesseract/Google Vision
- Automatic field extraction (date, amount, vendor, description)
- Structured data storage in PostgreSQL
- Validation workflow for extracted data

### 🔄 Reconciliation Module
- Upload ledger and bank statement files (CSV/Excel)
- Auto-match transactions by date and amount
- Configurable tolerance settings
- Flag unmatched records as exceptions
- Manual confirmation workflow

### 📊 Dashboard Module
- GraphQL API for financial metrics
- Real-time financial summaries
- Cashflow trend analysis
- Expense distribution charts
- Document and reconciliation statistics

### 📋 Report Generator
- PDF audit reports with charts and summaries
- Customizable report templates
- Background report generation with Celery
- Download and preview functionality

## Technology Stack

- **Backend**: Django 4.2.7, Django REST Framework
- **GraphQL**: Graphene-Django
- **Database**: PostgreSQL
- **Cache/Queue**: Redis
- **Background Tasks**: Celery
- **OCR**: Tesseract, Google Cloud Vision
- **File Processing**: Pandas, OpenPyXL
- **PDF Generation**: ReportLab, WeasyPrint
- **Containerization**: Docker, Docker Compose

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (for containerized deployment)

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd accounting-system
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run database migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create initial data**
   ```bash
   python manage.py setup_initial_data --create-superuser
   ```

7. **Start the development server**
   ```bash
   python manage.py runserver
   ```

8. **Start Celery worker (in separate terminal)**
   ```bash
   celery -A account worker -l info
   ```

### Docker Deployment

1. **Build and start services**
   ```bash
   docker-compose up -d
   ```

2. **Run migrations**
   ```bash
   docker-compose exec web python manage.py migrate
   ```

3. **Create initial data**
   ```bash
   docker-compose exec web python manage.py setup_initial_data --create-superuser
   ```

4. **Access the application**
   - API: http://localhost:8000
   - Admin: http://localhost:8000/admin
   - GraphQL: http://localhost:8000/graphql

## API Documentation

### REST API Endpoints

#### Documents
- `POST /api/documents/upload/` - Upload document
- `GET /api/documents/` - List documents
- `POST /api/documents/{id}/process/` - Start OCR processing
- `GET /api/documents/{id}/status/` - Check processing status
- `POST /api/documents/validate-field/{field_id}/` - Validate extracted field

#### Reconciliation
- `POST /api/reconciliation/upload-files/` - Upload reconciliation files
- `GET /api/reconciliation/sessions/` - List reconciliation sessions
- `POST /api/reconciliation/start-reconciliation/{session_id}/` - Start reconciliation
- `POST /api/reconciliation/confirm-match/{match_id}/` - Confirm transaction match
- `POST /api/reconciliation/resolve-exception/{exception_id}/` - Resolve exception

#### Reports
- `POST /api/reports/generate/` - Generate report
- `GET /api/reports/generated/` - List generated reports
- `GET /api/reports/download/{report_id}/` - Download report

### GraphQL Queries

#### Financial Metrics
```graphql
query {
  financialSummary(periodStart: "2024-01-01", periodEnd: "2024-12-31") {
    totalRevenue
    totalExpenses
    netProfit
    cashFlow
  }
}
```

#### Cashflow Trend
```graphql
query {
  cashflowTrend(periodStart: "2024-01-01", periodEnd: "2024-12-31", periodType: "monthly") {
    date
    inflow
    outflow
    netFlow
  }
}
```

#### Expense Breakdown
```graphql
query {
  expenseBreakdown(periodStart: "2024-01-01", periodEnd: "2024-12-31") {
    categoryName
    amount
    percentage
    colorCode
  }
}
```

## Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration
DB_NAME=accounting_db
DB_USER=postgres
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# OCR Configuration
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe

# Google Cloud Vision API (optional)
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
```

### OCR Setup

#### Tesseract (Local)
1. Download and install [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
2. Update `TESSERACT_CMD` in your `.env` file

#### Google Cloud Vision (Cloud)
1. Create a Google Cloud Project
2. Enable the Vision API
3. Create a service account and download credentials
4. Set `GOOGLE_APPLICATION_CREDENTIALS` in your `.env` file

## Usage Examples

### 1. Document Upload and Processing

```python
import requests

# Upload document
files = {'file': open('invoice.pdf', 'rb')}
data = {'document_type': 'invoice'}
response = requests.post('http://localhost:8000/api/documents/upload/', 
                        files=files, data=data)
document_id = response.json()['document']['id']

# Start processing
requests.post(f'http://localhost:8000/api/documents/process/{document_id}/')

# Check status
status = requests.get(f'http://localhost:8000/api/documents/{document_id}/status/')
```

### 2. Reconciliation

```python
# Upload reconciliation files
files = {
    'ledger_file': open('ledger.csv', 'rb'),
    'bank_statement_file': open('bank_statement.csv', 'rb')
}
data = {
    'name': 'Q1 2024 Reconciliation',
    'date_tolerance_days': 3,
    'amount_tolerance': '0.01'
}
response = requests.post('http://localhost:8000/api/reconciliation/upload-files/', 
                        files=files, data=data)
session_id = response.json()['session']['id']

# Start reconciliation
requests.post(f'http://localhost:8000/api/reconciliation/start-reconciliation/{session_id}/')
```

### 3. Generate Report

```python
data = {
    'template_id': 'audit_summary_template_id',
    'title': 'Q1 2024 Audit Report',
    'date_from': '2024-01-01',
    'date_to': '2024-03-31',
    'format': 'pdf'
}
response = requests.post('http://localhost:8000/api/reports/generate/', json=data)
```

## Development

### Project Structure
```
account/
├── account/              # Main Django project
├── documents/            # Document processing app
├── reconciliation/       # Reconciliation app  
├── dashboard/            # GraphQL API and metrics
├── reports/              # Report generation app
├── media/                # Uploaded files
├── static/               # Static files
├── templates/            # HTML templates
├── docker-compose.yml    # Docker configuration
├── Dockerfile            # Docker image definition
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

### Running Tests
```bash
python manage.py test
```

### Code Style
```bash
# Install development dependencies
pip install black flake8 isort

# Format code
black .
isort .

# Check style
flake8 .
```

## Monitoring and Logging

### Health Check
```bash
curl http://localhost:8000/health/
```

### Logs
- Application logs: `logs/django.log`
- Celery logs: Check Docker logs or console output

### Metrics
- Basic metrics: `GET /api/dashboard/metrics/`
- GraphQL metrics: `POST /graphql/`

## Troubleshooting

### Common Issues

1. **OCR not working**
   - Ensure Tesseract is installed and path is correct
   - Check file permissions
   - Verify supported file formats

2. **Celery tasks not processing**
   - Ensure Redis is running
   - Check Celery worker logs
   - Verify task registration

3. **File upload failures**
   - Check file size limits
   - Verify supported formats
   - Check disk space

4. **Database connection errors**
   - Verify PostgreSQL is running
   - Check connection parameters
   - Ensure database exists

### Performance Optimization

1. **Database**
   - Add indexes for frequently queried fields
   - Use database connection pooling
   - Optimize complex queries

2. **Caching**
   - Enable Redis caching
   - Cache GraphQL queries
   - Use template fragment caching

3. **File Processing**
   - Process large files asynchronously
   - Implement file chunking
   - Use background tasks

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue on GitHub
- Check the documentation
- Review the API endpoints

## Roadmap

- [ ] Machine learning for better field extraction
- [ ] Multi-currency support
- [ ] Advanced analytics and forecasting
- [ ] Mobile app support
- [ ] Integration with accounting software
- [ ] Advanced audit trail features
