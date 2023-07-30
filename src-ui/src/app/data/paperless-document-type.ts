import { MatchingModel } from './matching-model'
import { PaperlessIndexFieldMetadataDataItem } from './paperless-document-index-field-metadata'

export interface PaperlessDocumentType extends MatchingModel {
  default_metadata: PaperlessIndexFieldMetadataDataItem[]
}
