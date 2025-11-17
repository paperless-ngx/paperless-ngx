# IntelliDocs-ngx Technical Functions Guide

## Complete Function Reference

This document provides detailed documentation for all major functions in IntelliDocs-ngx.

---

## Table of Contents

1. [Documents Module Functions](#1-documents-module-functions)
2. [Paperless Core Functions](#2-paperless-core-functions)
3. [Mail Integration Functions](#3-mail-integration-functions)
4. [OCR & Parsing Functions](#4-ocr--parsing-functions)
5. [API & Serialization Functions](#5-api--serialization-functions)
6. [Frontend Services & Components](#6-frontend-services--components)
7. [Utility Functions](#7-utility-functions)
8. [Database Models & Methods](#8-database-models--methods)

---

## 1. Documents Module Functions

### 1.1 Consumer Module (`documents/consumer.py`)

#### Class: `Consumer`
Main class responsible for consuming and processing documents.

##### `__init__(self)`
```python
def __init__(self)
```
**Purpose**: Initialize the consumer with logging and configuration.

**Parameters**: None

**Returns**: Consumer instance

**Usage**:
```python
consumer = Consumer()
```

---

##### `try_consume_file(self, path, override_filename=None, override_title=None, ...)`
```python
def try_consume_file(
    self,
    path,
    override_filename=None,
    override_title=None,
    override_correspondent_id=None,
    override_document_type_id=None,
    override_tag_ids=None,
    override_created=None,
    override_asn=None,
    task_id=None,
    ...
)
```
**Purpose**: Entry point for consuming a document file.

**Parameters**:
- `path` (str): Full path to the document file
- `override_filename` (str, optional): Custom filename to use
- `override_title` (str, optional): Custom document title
- `override_correspondent_id` (int, optional): Force specific correspondent
- `override_document_type_id` (int, optional): Force specific document type
- `override_tag_ids` (list, optional): Force specific tags
- `override_created` (datetime, optional): Override creation date
- `override_asn` (int, optional): Archive serial number
- `task_id` (str, optional): Celery task ID for progress tracking

**Returns**: Document ID (int) or raises exception

**Raises**:
- `ConsumerError`: If document consumption fails
- `FileNotFoundError`: If file doesn't exist

**Process Flow**:
1. Validate file exists and is readable
2. Determine file type
3. Select appropriate parser
4. Extract text via OCR/parsing
5. Apply classification rules
6. Extract metadata
7. Create thumbnails
8. Save to database
9. Trigger post-consumption workflows
10. Cleanup temporary files

**Example**:
```python
doc_id = consumer.try_consume_file(
    path="/tmp/invoice.pdf",
    override_correspondent_id=5,
    override_tag_ids=[1, 3, 7]
)
```

---

##### `_consume(self, path, document, ...)`
```python
def _consume(self, path, document, metadata_from_path)
```
**Purpose**: Internal method that performs the actual document consumption.

**Parameters**:
- `path` (str): Path to document
- `document` (Document): Document model instance
- `metadata_from_path` (dict): Extracted metadata from filename

**Returns**: None (modifies document in place)

**Process**:
1. Parse document with selected parser
2. Extract text content
3. Store original file
4. Generate archive version
5. Create thumbnails
6. Index for search
7. Run classifier if enabled
8. Apply matching rules

---

##### `_write(self, document, path, original_filename, ...)`
```python
def _write(self, document, path, original_filename, original_checksum, ...):
```
**Purpose**: Save document to database and filesystem.

**Parameters**:
- `document` (Document): Document instance to save
- `path` (str): Source file path
- `original_filename` (str): Original filename
- `original_checksum` (str): MD5/SHA256 checksum

**Returns**: None

**Side Effects**:
- Saves document to database
- Moves files to final locations
- Creates backup entries
- Triggers post-save signals

---

### 1.2 Classifier Module (`documents/classifier.py`)

#### Class: `DocumentClassifier`
Implements machine learning classification for automatic document categorization.

##### `__init__(self)`
```python
def __init__(self)
```
**Purpose**: Initialize classifier with sklearn models.

**Components**:
- `vectorizer`: TfidfVectorizer for text feature extraction
- `correspondent_classifier`: LinearSVC for correspondent prediction
- `document_type_classifier`: LinearSVC for document type prediction
- `tag_classifier`: OneVsRestClassifier for multi-label tag prediction

---

##### `train(self)`
```python
def train(self) -> bool
```
**Purpose**: Train classification models on existing documents.

**Parameters**: None

**Returns**:
- `True` if training successful
- `False` if insufficient data

**Requirements**:
- Minimum 50 documents with correspondents for correspondent training
- Minimum 50 documents with document types for type training
- Minimum 50 documents with tags for tag training

**Process**:
1. Load all documents from database
2. Extract text features using TF-IDF
3. Train correspondent classifier
4. Train document type classifier
5. Train tag classifier (multi-label)
6. Save models to disk
7. Log accuracy metrics

**Example**:
```python
classifier = DocumentClassifier()
success = classifier.train()
if success:
    print("Classifier trained successfully")
```

---

##### `classify_document(self, document)`
```python
def classify_document(self, document) -> dict
```
**Purpose**: Predict classifications for a document.

**Parameters**:
- `document` (Document): Document to classify

**Returns**: Dictionary with predictions:
```python
{
    'correspondent': int or None,
    'document_type': int or None,
    'tags': list of int,
    'correspondent_confidence': float,
    'document_type_confidence': float,
    'tags_confidence': list of float
}
```

**Example**:
```python
predictions = classifier.classify_document(my_document)
print(f"Suggested correspondent: {predictions['correspondent']}")
print(f"Confidence: {predictions['correspondent_confidence']}")
```

---

##### `calculate_best_correspondent(self, document)`
```python
def calculate_best_correspondent(self, document) -> tuple
```
**Purpose**: Find the most likely correspondent for a document.

**Parameters**:
- `document` (Document): Document to analyze

**Returns**: `(correspondent_id, confidence_score)`

**Algorithm**:
1. Check for matching rules (highest priority)
2. If no match, use ML classifier
3. Calculate confidence based on decision function
4. Return correspondent if confidence > threshold

---

##### `calculate_best_document_type(self, document)`
```python
def calculate_best_document_type(self, document) -> tuple
```
**Purpose**: Determine the best document type classification.

**Parameters**:
- `document` (Document): Document to classify

**Returns**: `(document_type_id, confidence_score)`

**Similar to correspondent classification but for document types.**

---

##### `calculate_best_tags(self, document)`
```python
def calculate_best_tags(self, document) -> list
```
**Purpose**: Suggest relevant tags for a document.

**Parameters**:
- `document` (Document): Document to tag

**Returns**: List of `(tag_id, confidence_score)` tuples

**Multi-label Classification**:
- Can return multiple tags
- Each tag has independent confidence score
- Returns tags above confidence threshold

---

### 1.3 Index Module (`documents/index.py`)

#### Class: `DocumentIndex`
Manages full-text search indexing for documents.

##### `__init__(self, index_dir=None)`
```python
def __init__(self, index_dir=None)
```
**Purpose**: Initialize search index.

**Parameters**:
- `index_dir` (str, optional): Path to index directory

**Components**:
- Uses Whoosh library for indexing
- Creates schema with fields: id, title, content, correspondent, tags
- Supports stemming and stop words

---

##### `add_or_update_document(self, document)`
```python
def add_or_update_document(self, document) -> None
```
**Purpose**: Add or update a document in the search index.

**Parameters**:
- `document` (Document): Document to index

**Process**:
1. Extract searchable text
2. Tokenize and stem words
3. Build search index entry
4. Update or insert into index
5. Commit changes

**Example**:
```python
index = DocumentIndex()
index.add_or_update_document(my_document)
```

---

##### `remove_document(self, document_id)`
```python
def remove_document(self, document_id) -> None
```
**Purpose**: Remove a document from search index.

**Parameters**:
- `document_id` (int): ID of document to remove

---

##### `search(self, query_string, limit=50)`
```python
def search(self, query_string, limit=50) -> list
```
**Purpose**: Perform full-text search.

**Parameters**:
- `query_string` (str): Search query
- `limit` (int): Maximum results to return

**Returns**: List of document IDs, ranked by relevance

**Features**:
- Boolean operators (AND, OR, NOT)
- Phrase search ("exact phrase")
- Wildcard search (docu*)
- Field-specific search (title:invoice)
- Ranking by TF-IDF and BM25

**Example**:
```python
results = index.search("invoice AND 2023")
documents = Document.objects.filter(id__in=results)
```

---

### 1.4 Matching Module (`documents/matching.py`)

#### Class: `Match`
Represents a matching rule for automatic classification.

##### Properties:
- `matching_algorithm`: "any", "all", "literal", "regex", "fuzzy"
- `match`: Pattern to match
- `is_insensitive`: Case-insensitive matching

##### `matches(self, text)`
```python
def matches(self, text) -> bool
```
**Purpose**: Check if text matches this rule.

**Parameters**:
- `text` (str): Text to check

**Returns**: True if matches, False otherwise

**Algorithms**:
- **any**: Match if any word in pattern is in text
- **all**: Match if all words in pattern are in text
- **literal**: Exact substring match
- **regex**: Regular expression match
- **fuzzy**: Fuzzy string matching (Levenshtein distance)

---

#### Function: `match_correspondents(document, classifier=None)`
```python
def match_correspondents(document, classifier=None) -> int or None
```
**Purpose**: Find correspondent for document using rules and classifier.

**Parameters**:
- `document` (Document): Document to match
- `classifier` (DocumentClassifier, optional): ML classifier

**Returns**: Correspondent ID or None

**Process**:
1. Check manual assignment
2. Apply matching rules (in order of priority)
3. If no match, use ML classifier
4. Return correspondent if confidence sufficient

---

#### Function: `match_document_type(document, classifier=None)`
```python
def match_document_type(document, classifier=None) -> int or None
```
**Purpose**: Find document type using rules and classifier.

**Similar to correspondent matching.**

---

#### Function: `match_tags(document, classifier=None)`
```python
def match_tags(document, classifier=None) -> list
```
**Purpose**: Find matching tags using rules and classifier.

**Returns**: List of tag IDs

**Multi-label**: Can return multiple tags.

---

### 1.5 Barcode Module (`documents/barcodes.py`)

#### Function: `get_barcodes(path, pages=None)`
```python
def get_barcodes(path, pages=None) -> list
```
**Purpose**: Extract barcodes from document.

**Parameters**:
- `path` (str): Path to document
- `pages` (list, optional): Specific pages to scan

**Returns**: List of barcode dictionaries:
```python
[
    {
        'type': 'CODE128',
        'data': 'ABC123',
        'page': 1,
        'bbox': [x, y, w, h]
    },
    ...
]
```

**Supported Formats**:
- CODE128, CODE39, QR Code, Data Matrix, EAN, UPC

**Uses**:
- pyzbar library for barcode detection
- OpenCV for image processing

---

#### Function: `barcode_reader(path)`
```python
def barcode_reader(path) -> dict
```
**Purpose**: Read and interpret barcode data.

**Returns**: Parsed barcode information with metadata.

---

#### Function: `separate_pages(path, barcodes)`
```python
def separate_pages(path, barcodes) -> list
```
**Purpose**: Split document based on separator barcodes.

**Parameters**:
- `path` (str): Path to multi-page document
- `barcodes` (list): Detected barcodes with page numbers

**Returns**: List of paths to separated documents

**Use Case**:
- Batch scanning with separator sheets
- Automatic document splitting

**Example**:
```python
# Scan stack of documents with barcode separators
barcodes = get_barcodes("/tmp/batch.pdf")
documents = separate_pages("/tmp/batch.pdf", barcodes)
for doc_path in documents:
    consumer.try_consume_file(doc_path)
```

---

### 1.6 Bulk Edit Module (`documents/bulk_edit.py`)

#### Class: `BulkEditService`
Handles mass document operations efficiently.

##### `update_documents(self, document_ids, updates)`
```python
def update_documents(self, document_ids, updates) -> dict
```
**Purpose**: Update multiple documents at once.

**Parameters**:
- `document_ids` (list): List of document IDs
- `updates` (dict): Fields to update

**Returns**: Result summary:
```python
{
    'updated': 42,
    'failed': 0,
    'errors': []
}
```

**Supported Updates**:
- correspondent
- document_type
- tags (add, remove, replace)
- storage_path
- custom fields
- permissions

**Optimizations**:
- Batched database operations
- Minimal signal triggering
- Deferred index updates

**Example**:
```python
service = BulkEditService()
result = service.update_documents(
    document_ids=[1, 2, 3, 4, 5],
    updates={
        'document_type': 3,
        'tags_add': [7, 8],
        'tags_remove': [2]
    }
)
```

---

##### `merge_documents(self, document_ids, target_id=None)`
```python
def merge_documents(self, document_ids, target_id=None) -> int
```
**Purpose**: Combine multiple documents into one.

**Parameters**:
- `document_ids` (list): Documents to merge
- `target_id` (int, optional): ID of target document

**Returns**: ID of merged document

**Process**:
1. Combine PDFs
2. Merge metadata (tags, etc.)
3. Preserve all original files
4. Update search index
5. Delete source documents (soft delete)

---

##### `split_document(self, document_id, split_pages)`
```python
def split_document(self, document_id, split_pages) -> list
```
**Purpose**: Split a document into multiple documents.

**Parameters**:
- `document_id` (int): Document to split
- `split_pages` (list): Page ranges for each new document

**Returns**: List of new document IDs

**Example**:
```python
# Split 10-page document into 3 documents
new_docs = service.split_document(
    document_id=42,
    split_pages=[
        [1, 2, 3],      # First 3 pages
        [4, 5, 6, 7],   # Middle 4 pages
        [8, 9, 10]      # Last 3 pages
    ]
)
```

---

### 1.7 Workflow Module (`documents/workflows/`)

#### Class: `WorkflowEngine`
Executes automated document workflows.

##### `execute_workflow(self, workflow, document, trigger_type)`
```python
def execute_workflow(self, workflow, document, trigger_type) -> dict
```
**Purpose**: Run a workflow on a document.

**Parameters**:
- `workflow` (Workflow): Workflow definition
- `document` (Document): Target document
- `trigger_type` (str): What triggered this workflow

**Returns**: Execution result:
```python
{
    'success': True,
    'actions_executed': 5,
    'actions_failed': 0,
    'errors': []
}
```

**Workflow Components**:
1. **Triggers**:
   - consumption
   - manual
   - scheduled
   - webhook

2. **Conditions**:
   - Document properties
   - Content matching
   - Date ranges
   - Custom field values

3. **Actions**:
   - Set correspondent
   - Set document type
   - Add/remove tags
   - Set custom fields
   - Execute webhook
   - Send email
   - Run script

**Example Workflow**:
```python
workflow = {
    'name': 'Invoice Processing',
    'trigger': 'consumption',
    'conditions': [
        {'field': 'content', 'operator': 'contains', 'value': 'INVOICE'}
    ],
    'actions': [
        {'type': 'set_document_type', 'value': 2},
        {'type': 'add_tags', 'value': [5, 6]},
        {'type': 'webhook', 'url': 'https://api.example.com/invoice'}
    ]
}
```

---

## 2. Paperless Core Functions

### 2.1 Settings Module (`paperless/settings.py`)

#### Configuration Functions

##### `load_config_from_env()`
```python
def load_config_from_env() -> dict
```
**Purpose**: Load configuration from environment variables.

**Returns**: Configuration dictionary

**Environment Variables**:
- `PAPERLESS_DBHOST`: Database host
- `PAPERLESS_DBPORT`: Database port
- `PAPERLESS_OCR_LANGUAGE`: OCR languages
- `PAPERLESS_CONSUMER_POLLING`: Polling interval
- `PAPERLESS_TASK_WORKERS`: Number of workers
- `PAPERLESS_SECRET_KEY`: Django secret key

---

##### `validate_settings(settings)`
```python
def validate_settings(settings) -> list
```
**Purpose**: Validate configuration for errors.

**Returns**: List of validation errors

**Checks**:
- Required settings present
- Valid database configuration
- OCR languages available
- Storage paths exist
- Secret key security

---

### 2.2 Celery Module (`paperless/celery.py`)

#### Task Configuration

##### `@app.task`
Decorator for creating Celery tasks.

**Example**:
```python
@app.task(bind=True, max_retries=3)
def process_document(self, doc_id):
    try:
        document = Document.objects.get(id=doc_id)
        # Process document
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
```

---

##### Periodic Tasks

```python
@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # Run sanity check daily at 3:30 AM
    sender.add_periodic_task(
        crontab(hour=3, minute=30),
        sanity_check.s(),
        name='daily-sanity-check'
    )

    # Train classifier weekly
    sender.add_periodic_task(
        crontab(day_of_week=0, hour=2, minute=0),
        train_classifier.s(),
        name='weekly-classifier-training'
    )
```

---

### 2.3 Authentication Module (`paperless/auth.py`)

#### Class: `PaperlessRemoteUserBackend`
Custom authentication backend.

##### `authenticate(self, request, remote_user=None)`
```python
def authenticate(self, request, remote_user=None) -> User or None
```
**Purpose**: Authenticate user via HTTP header (SSO).

**Parameters**:
- `request`: HTTP request
- `remote_user`: Username from header

**Returns**: User instance or None

**Supports**:
- HTTP_REMOTE_USER header
- LDAP integration
- OAuth2 providers
- SAML

---

## 3. Mail Integration Functions

### 3.1 Mail Processing (`paperless_mail/mail.py`)

#### Class: `MailAccountHandler`

##### `get_messages(self, max_messages=100)`
```python
def get_messages(self, max_messages=100) -> list
```
**Purpose**: Fetch emails from mail account.

**Parameters**:
- `max_messages` (int): Maximum emails to fetch

**Returns**: List of email message objects

**Protocols**:
- IMAP
- IMAP with OAuth2 (Gmail, Outlook)

---

##### `process_message(self, message)`
```python
def process_message(self, message) -> Document or None
```
**Purpose**: Convert email to document.

**Parameters**:
- `message`: Email message object

**Returns**: Created document or None

**Process**:
1. Extract email metadata (from, to, subject, date)
2. Extract body text
3. Download attachments
4. Create document for email body
5. Create documents for attachments
6. Link documents together
7. Apply mail rules

---

##### `handle_attachments(self, message)`
```python
def handle_attachments(self, message) -> list
```
**Purpose**: Extract and process email attachments.

**Returns**: List of attachment file paths

**Supported**:
- PDF attachments
- Image attachments
- Office documents
- Archives (extracts)

---

## 4. OCR & Parsing Functions

### 4.1 Tesseract Parser (`paperless_tesseract/parsers.py`)

#### Class: `RasterisedDocumentParser`

##### `parse(self, document_path, mime_type)`
```python
def parse(self, document_path, mime_type) -> dict
```
**Purpose**: OCR document using Tesseract.

**Parameters**:
- `document_path` (str): Path to document
- `mime_type` (str): MIME type

**Returns**: Parsed document data:
```python
{
    'text': 'Extracted text content',
    'metadata': {...},
    'pages': 10,
    'language': 'eng'
}
```

**Process**:
1. Convert to images (if PDF)
2. Preprocess images (deskew, denoise)
3. Detect language
4. Run Tesseract OCR
5. Post-process text (fix common errors)
6. Create searchable PDF

---

##### `construct_ocrmypdf_parameters(self)`
```python
def construct_ocrmypdf_parameters(self) -> list
```
**Purpose**: Build command-line arguments for OCRmyPDF.

**Returns**: List of arguments

**Configuration**:
- Language selection
- OCR mode (redo, skip, force)
- Image preprocessing
- PDF/A creation
- Optimization level

---

### 4.2 Tika Parser (`paperless_tika/parsers.py`)

#### Class: `TikaDocumentParser`

##### `parse(self, document_path, mime_type)`
```python
def parse(self, document_path, mime_type) -> dict
```
**Purpose**: Parse document using Apache Tika.

**Supported Formats**:
- Microsoft Office (doc, docx, xls, xlsx, ppt, pptx)
- LibreOffice (odt, ods, odp)
- Rich Text Format (rtf)
- Archives (zip, tar, rar)
- Images with metadata

**Returns**: Parsed content and metadata

---

## 5. API & Serialization Functions

### 5.1 Document ViewSet (`documents/views.py`)

#### Class: `DocumentViewSet`

##### `list(self, request)`
```python
def list(self, request) -> Response
```
**Purpose**: List documents with filtering and pagination.

**Query Parameters**:
- `page`: Page number
- `page_size`: Results per page
- `ordering`: Sort field
- `correspondent__id`: Filter by correspondent
- `document_type__id`: Filter by type
- `tags__id__in`: Filter by tags
- `created__date__gt`: Filter by date
- `query`: Full-text search

**Response**:
```python
{
    'count': 100,
    'next': 'http://api/documents/?page=2',
    'previous': null,
    'results': [...]
}
```

---

##### `retrieve(self, request, pk=None)`
```python
def retrieve(self, request, pk=None) -> Response
```
**Purpose**: Get single document details.

**Parameters**:
- `pk`: Document ID

**Response**: Full document JSON with metadata

---

##### `download(self, request, pk=None)`
```python
@action(detail=True, methods=['get'])
def download(self, request, pk=None) -> FileResponse
```
**Purpose**: Download document file.

**Query Parameters**:
- `original`: Download original vs archive version

**Returns**: File download response

---

##### `preview(self, request, pk=None)`
```python
@action(detail=True, methods=['get'])
def preview(self, request, pk=None) -> FileResponse
```
**Purpose**: Generate document preview image.

**Returns**: PNG/JPEG image

---

##### `metadata(self, request, pk=None)`
```python
@action(detail=True, methods=['get'])
def metadata(self, request, pk=None) -> Response
```
**Purpose**: Get/update document metadata.

**GET Response**:
```python
{
    'original_filename': 'invoice.pdf',
    'media_filename': '0000042.pdf',
    'created': '2023-01-15T10:30:00Z',
    'modified': '2023-01-15T10:30:00Z',
    'added': '2023-01-15T10:30:00Z',
    'archive_checksum': 'sha256:abc123...',
    'original_checksum': 'sha256:def456...',
    'original_size': 245760,
    'archive_size': 180000,
    'original_mime_type': 'application/pdf'
}
```

---

##### `suggestions(self, request, pk=None)`
```python
@action(detail=True, methods=['get'])
def suggestions(self, request, pk=None) -> Response
```
**Purpose**: Get ML classification suggestions.

**Response**:
```python
{
    'correspondents': [
        {'id': 5, 'name': 'Acme Corp', 'confidence': 0.87},
        {'id': 2, 'name': 'Beta Inc', 'confidence': 0.12}
    ],
    'document_types': [...],
    'tags': [...]
}
```

---

##### `bulk_edit(self, request)`
```python
@action(detail=False, methods=['post'])
def bulk_edit(self, request) -> Response
```
**Purpose**: Bulk update multiple documents.

**Request Body**:
```python
{
    'documents': [1, 2, 3, 4, 5],
    'method': 'set_correspondent',
    'parameters': {'correspondent': 7}
}
```

**Methods**:
- `set_correspondent`
- `set_document_type`
- `set_storage_path`
- `add_tag` / `remove_tag`
- `modify_tags`
- `delete`
- `merge`
- `split`

---

## 6. Frontend Services & Components

### 6.1 Document Service (`src-ui/src/app/services/rest/document.service.ts`)

#### Class: `DocumentService`

##### `listFiltered(page, pageSize, sortField, sortReverse, filterRules, extraParams?)`
```typescript
listFiltered(
  page?: number,
  pageSize?: number,
  sortField?: string,
  sortReverse?: boolean,
  filterRules?: FilterRule[],
  extraParams?: any
): Observable<PaginatedResults<Document>>
```
**Purpose**: Get filtered list of documents.

**Parameters**:
- `page`: Page number (1-indexed)
- `pageSize`: Results per page
- `sortField`: Field to sort by
- `sortReverse`: Reverse sort order
- `filterRules`: Array of filter rules
- `extraParams`: Additional query parameters

**Returns**: Observable of paginated results

**Example**:
```typescript
this.documentService.listFiltered(
  1,
  50,
  'created',
  true,
  [
    {rule_type: FILTER_CORRESPONDENT, value: '5'},
    {rule_type: FILTER_HAS_TAGS_ALL, value: '1,3,7'}
  ]
).subscribe(results => {
  this.documents = results.results;
});
```

---

##### `get(id: number)`
```typescript
get(id: number): Observable<Document>
```
**Purpose**: Get single document by ID.

---

##### `update(document: Document)`
```typescript
update(document: Document): Observable<Document>
```
**Purpose**: Update document metadata.

---

##### `upload(formData: FormData)`
```typescript
upload(formData: FormData): Observable<any>
```
**Purpose**: Upload new document.

**FormData fields**:
- `document`: File
- `title`: Optional title
- `correspondent`: Optional correspondent ID
- `document_type`: Optional type ID
- `tags`: Optional tag IDs

---

##### `download(id: number, original: boolean)`
```typescript
download(id: number, original: boolean = false): Observable<Blob>
```
**Purpose**: Download document file.

---

##### `getPreviewUrl(id: number)`
```typescript
getPreviewUrl(id: number): string
```
**Purpose**: Get URL for document preview.

**Returns**: URL string

---

##### `getThumbUrl(id: number)`
```typescript
getThumbUrl(id: number): string
```
**Purpose**: Get URL for document thumbnail.

---

##### `bulkEdit(documentIds: number[], method: string, parameters: any)`
```typescript
bulkEdit(
  documentIds: number[],
  method: string,
  parameters: any
): Observable<any>
```
**Purpose**: Perform bulk operation on documents.

---

### 6.2 Search Service (`src-ui/src/app/services/search.service.ts`)

#### Class: `SearchService`

##### `search(query: string)`
```typescript
search(query: string): Observable<SearchResult[]>
```
**Purpose**: Perform full-text search.

**Query Syntax**:
- Simple: `invoice 2023`
- Phrase: `"exact phrase"`
- Boolean: `invoice AND 2023`
- Field: `title:invoice`
- Wildcard: `doc*`

---

##### `advancedSearch(query: SearchQuery)`
```typescript
advancedSearch(query: SearchQuery): Observable<SearchResult[]>
```
**Purpose**: Advanced search with multiple criteria.

**SearchQuery**:
```typescript
interface SearchQuery {
  text?: string;
  correspondent?: number;
  documentType?: number;
  tags?: number[];
  dateFrom?: Date;
  dateTo?: Date;
  customFields?: {[key: string]: any};
}
```

---

### 6.3 Settings Service (`src-ui/src/app/services/settings.service.ts`)

#### Class: `SettingsService`

##### `getSettings()`
```typescript
getSettings(): Observable<PaperlessSettings>
```
**Purpose**: Get user/system settings.

---

##### `updateSettings(settings: PaperlessSettings)`
```typescript
updateSettings(settings: PaperlessSettings): Observable<PaperlessSettings>
```
**Purpose**: Update settings.

---

## 7. Utility Functions

### 7.1 File Handling Utilities (`documents/file_handling.py`)

#### `generate_unique_filename(filename, suffix="")`
```python
def generate_unique_filename(filename, suffix="") -> str
```
**Purpose**: Generate unique filename to avoid collisions.

**Parameters**:
- `filename` (str): Base filename
- `suffix` (str): Optional suffix

**Returns**: Unique filename with timestamp

---

#### `create_source_path_directory(source_path)`
```python
def create_source_path_directory(source_path) -> None
```
**Purpose**: Create directory structure for document storage.

**Parameters**:
- `source_path` (str): Path template with variables

**Variables**:
- `{correspondent}`: Correspondent name
- `{document_type}`: Document type
- `{created}`: Creation date
- `{created_year}`: Year
- `{created_month}`: Month
- `{title}`: Document title
- `{asn}`: Archive serial number

**Example**:
```python
# Template: {correspondent}/{created_year}/{document_type}
# Result: Acme Corp/2023/Invoices/
```

---

#### `safe_rename(old_path, new_path)`
```python
def safe_rename(old_path, new_path) -> None
```
**Purpose**: Safely rename file with atomic operation.

**Ensures**: No data loss if operation fails

---

### 7.2 Data Utilities (`paperless/utils.py`)

#### `copy_basic_file_stats(src, dst)`
```python
def copy_basic_file_stats(src, dst) -> None
```
**Purpose**: Copy file metadata (timestamps, permissions).

---

#### `maybe_override_pixel_limit()`
```python
def maybe_override_pixel_limit() -> None
```
**Purpose**: Increase PIL image size limit for large documents.

---

## 8. Database Models & Methods

### 8.1 Document Model (`documents/models.py`)

#### Class: `Document`

##### Model Fields:
```python
class Document(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    correspondent = models.ForeignKey(Correspondent, ...)
    document_type = models.ForeignKey(DocumentType, ...)
    tags = models.ManyToManyField(Tag, ...)
    created = models.DateTimeField(...)
    modified = models.DateTimeField(auto_now=True)
    added = models.DateTimeField(auto_now_add=True)
    storage_path = models.ForeignKey(StoragePath, ...)
    archive_serial_number = models.IntegerField(...)
    original_filename = models.CharField(max_length=1024)
    checksum = models.CharField(max_length=64)
    archive_checksum = models.CharField(max_length=64)
    owner = models.ForeignKey(User, ...)
    custom_fields = models.ManyToManyField(CustomField, ...)
```

---

##### `save(self, *args, **kwargs)`
```python
def save(self, *args, **kwargs) -> None
```
**Purpose**: Override save to add custom logic.

**Custom Logic**:
1. Generate archive serial number if not set
2. Update modification timestamp
3. Trigger signals
4. Update search index

---

##### `filename(self)`
```python
@property
def filename(self) -> str
```
**Purpose**: Get the document filename.

**Returns**: Formatted filename based on template

---

##### `source_path(self)`
```python
@property
def source_path(self) -> str
```
**Purpose**: Get full path to source file.

---

##### `archive_path(self)`
```python
@property
def archive_path(self) -> str
```
**Purpose**: Get full path to archive file.

---

##### `get_public_filename(self)`
```python
def get_public_filename(self) -> str
```
**Purpose**: Get sanitized filename for downloads.

**Returns**: Safe filename without path traversal characters

---

### 8.2 Correspondent Model

#### Class: `Correspondent`

```python
class Correspondent(models.Model):
    name = models.CharField(max_length=255, unique=True)
    match = models.CharField(max_length=255, blank=True)
    matching_algorithm = models.IntegerField(choices=MATCH_CHOICES)
    is_insensitive = models.BooleanField(default=True)
    document_count = models.IntegerField(default=0)
    last_correspondence = models.DateTimeField(null=True)
    owner = models.ForeignKey(User, ...)
```

---

### 8.3 Workflow Model

#### Class: `Workflow`

```python
class Workflow(models.Model):
    name = models.CharField(max_length=255)
    enabled = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    triggers = models.ManyToManyField(WorkflowTrigger)
    conditions = models.ManyToManyField(WorkflowCondition)
    actions = models.ManyToManyField(WorkflowAction)
```

---

## Summary

This guide provides comprehensive documentation for the major functions in IntelliDocs-ngx. For detailed API documentation, refer to:

- **Backend API**: `/api/schema/` (OpenAPI/Swagger)
- **Frontend Docs**: Generated via Compodoc
- **Database Schema**: Django migrations in `migrations/` directories

For implementation examples and testing, see the test files in each module's `tests/` directory.

---

*Last Updated: 2025-11-09*
*Version: 2.19.5*
