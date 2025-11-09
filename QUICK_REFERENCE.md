# IntelliDocs-ngx - Quick Reference Guide

## 🎯 One-Page Overview

### What is IntelliDocs-ngx?
A document management system that scans, organizes, and searches your documents using AI and OCR.

### Tech Stack
- **Backend**: Django 5.2 + Python 3.10+
- **Frontend**: Angular 20 + TypeScript
- **Database**: PostgreSQL/MySQL
- **Queue**: Celery + Redis
- **OCR**: Tesseract + Tika

---

## 📁 Project Structure

```
IntelliDocs-ngx/
├── src/                          # Backend (Python/Django)
│   ├── documents/                # Core document management
│   │   ├── consumer.py          # Document ingestion
│   │   ├── classifier.py        # ML classification
│   │   ├── index.py             # Search indexing
│   │   ├── matching.py          # Auto-classification rules
│   │   ├── models.py            # Database models
│   │   ├── views.py             # REST API endpoints
│   │   └── tasks.py             # Background tasks
│   ├── paperless/               # Core framework
│   │   ├── settings.py          # Configuration
│   │   ├── celery.py            # Task queue
│   │   └── urls.py              # URL routing
│   ├── paperless_mail/          # Email integration
│   ├── paperless_tesseract/     # Tesseract OCR
│   ├── paperless_text/          # Text extraction
│   └── paperless_tika/          # Tika parsing
│
├── src-ui/                       # Frontend (Angular)
│   ├── src/
│   │   ├── app/
│   │   │   ├── components/      # UI components
│   │   │   ├── services/        # API services
│   │   │   └── models/          # TypeScript models
│   │   └── assets/              # Static files
│
├── docs/                         # User documentation
├── docker/                       # Docker configurations
└── scripts/                      # Utility scripts
```

---

## 🔑 Key Concepts

### Document Lifecycle
```
1. Upload → 2. OCR → 3. Classify → 4. Index → 5. Archive
```

### Components
- **Consumer**: Processes incoming documents
- **Classifier**: Auto-assigns tags/types using ML
- **Index**: Makes documents searchable
- **Workflow**: Automates document actions
- **API**: Exposes functionality to frontend

---

## 📊 Module Map

| Module | Purpose | Key Files |
|--------|---------|-----------|
| **documents** | Core DMS | consumer.py, classifier.py, models.py, views.py |
| **paperless** | Framework | settings.py, celery.py, auth.py |
| **paperless_mail** | Email import | mail.py, oauth.py |
| **paperless_tesseract** | OCR engine | parsers.py |
| **paperless_text** | Text extraction | parsers.py |
| **paperless_tika** | Format parsing | parsers.py |

---

## 🔧 Common Tasks

### Add New Document
```python
from documents.consumer import Consumer

consumer = Consumer()
doc_id = consumer.try_consume_file(
    path="/path/to/document.pdf",
    override_correspondent_id=5,
    override_tag_ids=[1, 3, 7]
)
```

### Search Documents
```python
from documents.index import DocumentIndex

index = DocumentIndex()
results = index.search("invoice 2023")
```

### Train Classifier
```python
from documents.classifier import DocumentClassifier

classifier = DocumentClassifier()
classifier.train()
```

### Create Workflow
```python
from documents.models import Workflow, WorkflowAction

workflow = Workflow.objects.create(
    name="Auto-file invoices",
    enabled=True
)

action = WorkflowAction.objects.create(
    workflow=workflow,
    type="set_document_type",
    value=2  # Invoice type ID
)
```

---

## 🌐 API Endpoints

### Documents
```
GET    /api/documents/              # List documents
GET    /api/documents/{id}/         # Get document
POST   /api/documents/              # Upload document
PATCH  /api/documents/{id}/         # Update document
DELETE /api/documents/{id}/         # Delete document
GET    /api/documents/{id}/download/ # Download file
GET    /api/documents/{id}/preview/  # Get preview
POST   /api/documents/bulk_edit/    # Bulk operations
```

### Search
```
GET    /api/search/?query=invoice   # Full-text search
```

### Metadata
```
GET    /api/correspondents/         # List correspondents
GET    /api/document_types/         # List types
GET    /api/tags/                   # List tags
GET    /api/storage_paths/          # List storage paths
```

### Workflows
```
GET    /api/workflows/              # List workflows
POST   /api/workflows/              # Create workflow
```

---

## 🎨 Frontend Components

### Main Components
- `DocumentListComponent` - Document grid view
- `DocumentDetailComponent` - Single document view
- `DocumentEditComponent` - Edit document metadata
- `SearchComponent` - Search interface
- `SettingsComponent` - Configuration UI

### Key Services
- `DocumentService` - API calls for documents
- `SearchService` - Search functionality
- `PermissionsService` - Access control
- `SettingsService` - User settings

---

## 🗄️ Database Models

### Core Models
```python
Document
├── title: CharField
├── content: TextField
├── correspondent: ForeignKey → Correspondent
├── document_type: ForeignKey → DocumentType
├── tags: ManyToManyField → Tag
├── storage_path: ForeignKey → StoragePath
├── created: DateTimeField
├── modified: DateTimeField
├── owner: ForeignKey → User
└── custom_fields: ManyToManyField → CustomFieldInstance

Correspondent
├── name: CharField
├── match: CharField
└── matching_algorithm: IntegerField

DocumentType
├── name: CharField
└── match: CharField

Tag
├── name: CharField
├── color: CharField
└── is_inbox_tag: BooleanField

Workflow
├── name: CharField
├── enabled: BooleanField
├── triggers: ManyToManyField → WorkflowTrigger
└── actions: ManyToManyField → WorkflowAction
```

---

## ⚡ Performance Tips

### Backend
```python
# ✅ Good: Use select_related for ForeignKey
documents = Document.objects.select_related(
    'correspondent', 'document_type'
).all()

# ✅ Good: Use prefetch_related for ManyToMany
documents = Document.objects.prefetch_related(
    'tags', 'custom_fields'
).all()

# ❌ Bad: N+1 queries
for doc in Document.objects.all():
    print(doc.correspondent.name)  # Extra query each time!
```

### Caching
```python
from django.core.cache import cache

# Cache expensive operations
def get_document_stats():
    stats = cache.get('document_stats')
    if stats is None:
        stats = calculate_stats()
        cache.set('document_stats', stats, 3600)
    return stats
```

### Database Indexes
```python
# Add indexes in migrations
migrations.AddIndex(
    model_name='document',
    index=models.Index(
        fields=['correspondent', 'created'],
        name='doc_corr_created_idx'
    )
)
```

---

## 🔒 Security Checklist

- [ ] Validate all user inputs
- [ ] Use parameterized queries (Django ORM does this)
- [ ] Check permissions on all endpoints
- [ ] Implement rate limiting
- [ ] Add security headers
- [ ] Enable HTTPS
- [ ] Use strong password hashing
- [ ] Implement CSRF protection
- [ ] Sanitize file uploads
- [ ] Regular dependency updates

---

## 🐛 Debugging Tips

### Backend
```python
# Add logging
import logging
logger = logging.getLogger(__name__)

def my_function():
    logger.debug("Debug information")
    logger.info("Important event")
    logger.error("Something went wrong")

# Django shell
python manage.py shell
>>> from documents.models import Document
>>> Document.objects.count()

# Run tests
python manage.py test documents
```

### Frontend
```typescript
// Console logging
console.log('Debug:', someVariable);
console.error('Error:', error);

// Angular DevTools
// Install Chrome extension for debugging

// Check network requests
// Use browser DevTools Network tab
```

### Celery Tasks
```bash
# View running tasks
celery -A paperless inspect active

# View scheduled tasks
celery -A paperless inspect scheduled

# Purge queue
celery -A paperless purge
```

---

## 📦 Common Commands

### Development
```bash
# Start development server
python manage.py runserver

# Start Celery worker
celery -A paperless worker -l INFO

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start frontend dev server
cd src-ui && ng serve
```

### Testing
```bash
# Run backend tests
python manage.py test

# Run frontend tests
cd src-ui && npm test

# Run specific test
python manage.py test documents.tests.test_consumer
```

### Production
```bash
# Collect static files
python manage.py collectstatic

# Check deployment
python manage.py check --deploy

# Start with Gunicorn
gunicorn paperless.wsgi:application
```

---

## 🔍 Troubleshooting

### Document not consuming
1. Check file permissions
2. Check Celery is running
3. Check logs: `docker logs paperless-worker`
4. Verify OCR languages installed

### Search not working
1. Rebuild index: `python manage.py document_index reindex`
2. Check Whoosh index permissions
3. Verify search settings

### Classification not accurate
1. Train classifier: `python manage.py document_classifier train`
2. Need 50+ documents per category
3. Check matching rules

### Frontend not loading
1. Check CORS settings
2. Verify API_URL configuration
3. Check browser console for errors
4. Clear browser cache

---

## 📈 Monitoring

### Key Metrics to Track
- Document processing rate (docs/minute)
- API response time (ms)
- Search query time (ms)
- Celery queue length
- Database query count
- Storage usage (GB)
- Error rate (%)

### Health Checks
```python
# Add to views.py
def health_check(request):
    checks = {
        'database': check_database(),
        'celery': check_celery(),
        'redis': check_redis(),
        'storage': check_storage(),
    }
    return JsonResponse(checks)
```

---

## 🎓 Learning Resources

### Python/Django
- Django Docs: https://docs.djangoproject.com/
- Celery Docs: https://docs.celeryproject.org/
- Django REST Framework: https://www.django-rest-framework.org/

### Frontend
- Angular Docs: https://angular.io/docs
- TypeScript: https://www.typescriptlang.org/docs/
- RxJS: https://rxjs.dev/

### Machine Learning
- scikit-learn: https://scikit-learn.org/
- Transformers: https://huggingface.co/docs/transformers/

### OCR
- Tesseract: https://github.com/tesseract-ocr/tesseract
- Apache Tika: https://tika.apache.org/

---

## 🚀 Quick Improvements

### 5-Minute Fixes
1. Add database index: +3x query speed
2. Enable gzip compression: +50% faster transfers
3. Add security headers: Better security score

### 1-Hour Improvements
1. Implement Redis caching: +2x API speed
2. Add lazy loading: +50% faster page load
3. Optimize images: Smaller bundle size

### 1-Day Projects
1. Frontend code splitting: Better performance
2. Add API rate limiting: DoS protection
3. Implement proper logging: Better debugging

### 1-Week Projects
1. Database optimization: 5-10x faster queries
2. Improve classification: +20% accuracy
3. Add mobile responsive: Better mobile UX

---

## 💡 Best Practices

### Code Style
```python
# ✅ Good
def process_document(document_id: int) -> Document:
    """Process a document and return the result.
    
    Args:
        document_id: ID of document to process
        
    Returns:
        Processed document instance
    """
    document = Document.objects.get(id=document_id)
    # ... processing logic
    return document

# ❌ Bad
def proc(d):
    x = Document.objects.get(id=d)
    return x
```

### Error Handling
```python
# ✅ Good
try:
    document = Document.objects.get(id=doc_id)
except Document.DoesNotExist:
    logger.error(f"Document {doc_id} not found")
    raise Http404("Document not found")
except Exception as e:
    logger.exception("Unexpected error")
    raise

# ❌ Bad
try:
    document = Document.objects.get(id=doc_id)
except:
    pass  # Silent failure!
```

### Testing
```python
# ✅ Good: Test important functionality
class DocumentConsumerTest(TestCase):
    def test_consume_pdf(self):
        doc_id = consumer.try_consume_file('/path/to/test.pdf')
        document = Document.objects.get(id=doc_id)
        self.assertIsNotNone(document.content)
        self.assertEqual(document.title, 'test')
```

---

## 📞 Getting Help

### Documentation Files
1. **DOCS_README.md** - Start here
2. **EXECUTIVE_SUMMARY.md** - High-level overview
3. **DOCUMENTATION_ANALYSIS.md** - Detailed analysis
4. **TECHNICAL_FUNCTIONS_GUIDE.md** - Function reference
5. **IMPROVEMENT_ROADMAP.md** - Implementation guide
6. **QUICK_REFERENCE.md** - This file!

### When Stuck
1. Check this quick reference
2. Review function documentation
3. Look at test files for examples
4. Check Django/Angular docs
5. Review original Paperless-ngx docs

---

## ✅ Pre-deployment Checklist

- [ ] All tests passing
- [ ] Code coverage > 80%
- [ ] Security scan completed
- [ ] Performance tests passed
- [ ] Documentation updated
- [ ] Backup strategy in place
- [ ] Monitoring configured
- [ ] Error tracking setup
- [ ] SSL/HTTPS enabled
- [ ] Environment variables configured
- [ ] Database optimized
- [ ] Static files collected
- [ ] Migrations applied
- [ ] Health check endpoint working

---

*Last Updated: November 9, 2025*  
*Version: 1.0*  
*IntelliDocs-ngx v2.19.5*
