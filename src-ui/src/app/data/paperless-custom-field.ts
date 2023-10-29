import { ObjectWithId } from './object-with-id'

export enum PaperlessCustomFieldDataType {
  String = 'string',
  Url = 'url',
  Date = 'date',
  Boolean = 'boolean',
  Integer = 'integer',
}

export const DATA_TYPE_LABELS = [
  {
    id: PaperlessCustomFieldDataType.Boolean,
    name: $localize`Boolean`,
  },
  {
    id: PaperlessCustomFieldDataType.Date,
    name: $localize`Date`,
  },
  {
    id: PaperlessCustomFieldDataType.Integer,
    name: $localize`Number`,
  },
  {
    id: PaperlessCustomFieldDataType.String,
    name: $localize`String`,
  },
  {
    id: PaperlessCustomFieldDataType.Url,
    name: $localize`Url`,
  },
]

export interface PaperlessCustomField extends ObjectWithId {
  data_type: PaperlessCustomFieldDataType
  name: string
  created?: Date
}
