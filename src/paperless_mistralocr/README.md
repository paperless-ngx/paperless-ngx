# Paperless Mistral OCR

This module integrates Mistral AI's OCR API for text extraction and document understanding in the Paperless-ngx document management system.

## Features

- Uses Mistral's advanced OCR API for extracting text from documents
- Supports PDFs and various image formats
- Improves metadata extraction through AI document understanding
- Seamlessly integrates with the existing Paperless workflow

## Installation

This module is included in Paperless-ngx. To enable it:

1. Install the required Python package:

   ```
   pip install mistralai
   ```

2. Get an API key from [Mistral AI](https://console.mistral.ai/)

3. Set the API key as an environment variable:

   ```
   PAPERLESS_MISTRAL_API_KEY=your_api_key_here
   ```

4. Optionally configure the model (defaults to "mistral-ocr-latest"):
   ```
   PAPERLESS_MISTRAL_MODEL=mistral-ocr-latest
   ```

## Configuration

The module uses the following configuration options:

| Environment Variable      | Description            | Default            |
| ------------------------- | ---------------------- | ------------------ |
| PAPERLESS_MISTRAL_API_KEY | API key for Mistral AI | (required)         |
| PAPERLESS_MISTRAL_MODEL   | Model to use for OCR   | mistral-ocr-latest |

The module also inherits other OCR settings from Paperless-ngx, such as:

- OCR_MODE (skip, redo, force)
- OCR_OUTPUT_TYPE (pdf, pdfa, etc.)

## Usage

Once configured, the module will automatically be used for OCR processing during document consumption. No additional steps are needed.

## How It Works

1. When a document is added to the consumption directory, the Mistral OCR parser is selected based on the file's MIME type
2. The document is sent to Mistral's OCR API for processing
3. The API returns the extracted text and document structure in markdown format
4. The text is extracted and stored with the document
5. Metadata like dates are automatically detected
6. The document is indexed for searching

## Limitations

- Files must be under 50MB due to Mistral API limitations
- Requires internet connectivity to process documents
- API usage may incur costs depending on your Mistral AI subscription plan

## Troubleshooting

Check the logs for any errors related to API connectivity or document processing:

```
docker-compose logs -f paperless
```

Common issues:

- Missing or invalid API key
- Network connectivity problems
- Missing mistralai Python package
- Document size limitations
