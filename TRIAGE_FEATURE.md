# Inbox Triage Mode Feature

## Overview

The Inbox Triage Mode is a new feature that allows users to quickly process inbox documents in a dedicated interface, similar to email triage workflows. This feature is designed to minimize mouse usage and speed up the review and filing of newly-ingested documents.

## Implementation

### Files Created

1. **`src-ui/src/app/services/triage.service.ts`**
   - Manages triage state (document queue, current index, filter rules, return URL)
   - Implements undo stack for reversing actions
   - Provides methods for navigation (next, previous, remove document)

2. **`src-ui/src/app/components/document-triage/document-triage.component.ts`**
   - Main triage component with document preview and metadata editor
   - Handles keyboard shortcuts
   - Integrates with existing document service for CRUD operations

3. **`src-ui/src/app/components/document-triage/document-triage.component.html`**
   - Split-pane layout: preview on left, metadata editor on right
   - Action buttons with keyboard shortcut hints
   - Empty state when queue is processed

4. **`src-ui/src/app/components/document-triage/document-triage.component.scss`**
   - Responsive layout styles
   - Preview panel with PDF viewer integration
   - Metadata panel with form inputs

5. **`src-ui/src/app/services/triage.service.spec.ts`**
   - Unit tests for the triage service

### Files Modified

1. **`src-ui/src/app/app-routing.module.ts`**
   - Added `/triage` route with permissions guard

2. **`src-ui/src/app/components/document-list/document-list.component.html`**
   - Added "Start Triage" button in page header (visible when on inbox view)

3. **`src-ui/src/app/components/document-list/document-list.component.ts`**
   - Added `startTriage()` method to load documents and initialize triage
   - Added `isInboxView()` helper to determine if current view is inbox

## Features

### Entry Points

1. **"Start Triage" button** - Appears in the document list page header when viewing inbox documents
2. Button is disabled when:
   - No documents are available
   - Not viewing an inbox-filtered list

### Triage Screen Layout

- **Left pane**: Document preview using existing PDF viewer component
- **Right pane**: Metadata editor with:
  - Tags (autocomplete)
  - Correspondent (dropdown)
  - Document type (dropdown)
  - Created date (date picker)
  - Action buttons with keyboard hints
  - Keyboard shortcuts reference

### Triage Flow

1. Load documents matching current filter (up to 100 documents)
2. Display first document with preview and metadata form
3. User edits metadata and clicks:
   - **"Archive & Next"** - Removes inbox tags and advances to next document
   - **"Save & Next"** - Saves metadata changes and advances to next document
4. Document is removed from queue after archiving
5. When queue is empty, show empty state with "Back to Documents" button
6. Exit returns user to original list view with filters preserved

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `N` | Next document |
| `P` | Previous document |
| `T` | Focus tag input |
| `C` | Focus correspondent input |
| `A` | Archive & Next (remove inbox tags and move to next) |
| `U` | Undo last action |
| `Esc` | Exit triage mode |

**Note**: Keyboard shortcuts are disabled when typing in input fields to prevent conflicts.

### Undo Functionality

- **Undo stack** stores up to 10 actions
- Each action records:
  - Document ID
  - Previous field values (tags, correspondent, document_type, created)
  - Action type (metadata or archive)
- Pressing `U` or clicking "Undo":
  - Restores previous values via API
  - If undoing an archive action, adds document back to queue
  - Shows toast notification

### State Management

- Triage state is stored in `TriageService`
- Includes:
  - Document queue
  - Current index
  - Original filter rules
  - Return URL
- State is cleared when exiting triage
- Return URL ensures user goes back to original view

## API Usage

The feature uses existing REST API endpoints:

- **`DocumentService.listFiltered()`** - Load documents for triage queue
- **`DocumentService.patch()`** - Update document metadata
- **`DocumentService.getPreviewUrl()`** - Get PDF preview URL
- **`CorrespondentService.listAll()`** - Load correspondents
- **`DocumentTypeService.listAll()`** - Load document types
- **`TagService.listAll()`** - Load tags

No new backend API endpoints were required.

## Testing

### Manual Testing Instructions

1. **Start the development server:**
   ```bash
   cd src-ui
   npm install  # or pnpm install
   ng serve
   ```

2. **Access the application:**
   - Navigate to `http://localhost:4200`
   - Log in with valid credentials

3. **Test the triage feature:**

   a. **Entry point:**
      - Go to Documents list
      - Apply an inbox filter (or use a saved view with inbox documents)
      - Click "Start Triage" button in the page header

   b. **Triage functionality:**
      - Verify document preview loads on the left
      - Edit tags, correspondent, document type, and date on the right
      - Test keyboard shortcuts:
        - Press `T` to focus tags input
        - Press `C` to focus correspondent input
        - Press `N` to move to next document
        - Press `P` to move to previous document
      
   c. **Save and Archive:**
      - Click "Save & Next" to save changes and advance
      - Click "Archive & Next" to remove inbox tags and advance
      - Verify documents are removed from queue after archiving
   
   d. **Undo:**
      - Make a change (e.g., add a tag)
      - Click "Archive & Next"
      - Press `U` to undo
      - Verify document is restored to queue with previous values
   
   e. **Exit:**
      - Press `Esc` or click "Exit"
      - Verify you return to the original document list with filters intact

   f. **Empty state:**
      - Process all documents in queue
      - Verify empty state appears with "Back to Documents" button

4. **Verify persistence:**
   - After archiving documents, navigate to document detail view
   - Confirm changes were saved and inbox tags were removed

### Unit Tests

Run the test suite:
```bash
cd src-ui
npm test  # or pnpm test
```

The `triage.service.spec.ts` file includes tests for:
- Initialization
- Navigation (next, previous)
- Document removal
- Undo stack operations
- State management

## Code Quality

- **No linting errors** - Code passes all ESLint checks
- **TypeScript strict mode** - Full type safety
- **Consistent style** - Follows existing codebase patterns
- **Reusable components** - Leverages existing input components, services, and pipes

## Future Enhancements

Potential improvements for future iterations:

1. **Bulk operations** - Allow selecting multiple documents for batch metadata updates
2. **Configurable shortcuts** - Let users customize keyboard shortcuts
3. **Progress persistence** - Save triage progress to resume later
4. **Advanced undo** - Support multi-level undo (currently 1-10 levels)
5. **Document splitting** - Integrate with split/merge tools during triage
6. **Custom fields** - Add custom field editing to triage interface
7. **Suggestions** - Show AI-powered suggestions for metadata
8. **Mobile optimization** - Improve touch-friendly controls for tablets

## Developer Notes

- The feature is implemented as a standalone route (`/triage`) to avoid disrupting existing document list functionality
- Triage state is managed separately from document list state
- The component reuses existing services and input components for consistency
- Keyboard shortcuts use the existing `HotKeyService` to prevent conflicts with other shortcuts
- PDF preview integrates with the same viewer used in document detail view
- The "Start Triage" button only appears when relevant (inbox view with documents)

## Troubleshooting

**Issue**: "Start Triage" button is disabled
- **Solution**: Make sure you're viewing documents with an inbox filter applied

**Issue**: Keyboard shortcuts not working
- **Solution**: Ensure no input field has focus. Click outside inputs first.

**Issue**: Preview not loading
- **Solution**: Check browser console for errors. Ensure PDF viewer is configured correctly.

**Issue**: Changes not saving
- **Solution**: Check network tab for API errors. Verify user has edit permissions.

## Acceptance Criteria ✅

- [x] User can process inbox docs without using the mouse (except initial click to start)
- [x] Edits persist (verified by reloading document detail view)
- [x] Undo works for the last triage action (supports up to 10 actions)
- [x] No lint/test failures introduced
- [x] Code style consistent with existing codebase
- [x] Keyboard shortcuts don't interfere with typing in inputs
- [x] User returns to same list view + filters when exiting triage
- [x] Empty state shown when queue is empty
- [x] Triage doesn't require page refresh

