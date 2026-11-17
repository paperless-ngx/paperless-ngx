import { getDocumentOperationLabel } from './document-operation'

describe('Document Operation Utils', () => {
  it('should retrieve the document operation label correctly for an existing operation, null otherwise', () => {
    const result = getDocumentOperationLabel('modify_custom_fields')
    expect(result).toBe('Update custom fields')

    const resultNull = getDocumentOperationLabel('non_existing_operation')
    expect(resultNull).toBeNull()
  })
})
