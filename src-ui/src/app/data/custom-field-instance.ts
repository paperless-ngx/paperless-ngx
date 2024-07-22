import { ObjectWithId } from './object-with-id'

export interface CustomFieldInstance extends ObjectWithId {
  document?: number // Document
  field: number // CustomField
  created?: Date
  value?: any
  field_name?: string 
  dossier?: number // dossier
  match_value?: string;
  dossier_document?: number;
  reference?: number;
  // match?: any;
}
