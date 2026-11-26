import {
  documentOperationHasFollowUpTasks,
  getDocumentOperationLabel,
} from './document-operation'

describe('Document Operation Utils', () => {
  it('names zone OCR and treats task completion as finished extraction', () => {
    expect(getDocumentOperationLabel('run_zone_ocr')).toBe('Run zone OCR')
    expect(documentOperationHasFollowUpTasks('run_zone_ocr')).toBe(false)
  })
  it('should retrieve the document operation label correctly for an existing operation, null otherwise', () => {
    const result = getDocumentOperationLabel('modify_custom_fields')
    expect(result).toBe('Update custom fields')

    const resultNull = getDocumentOperationLabel('non_existing_operation')
    expect(resultNull).toBeNull()
  })
})
