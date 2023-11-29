import { ObjectWithId } from './object-with-id'

export enum PaperlessCustomFieldDataType {
  String = 'string',
  Url = 'url',
  Date = 'date',
  Boolean = 'boolean',
  Integer = 'integer',
  Float = 'float',
  Monetary = 'monetary',
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
    name: $localize`Integer`,
  },
  {
    id: PaperlessCustomFieldDataType.Float,
    name: $localize`Number`,
  },
  {
    id: PaperlessCustomFieldDataType.Monetary,
    name: $localize`Monetary`,
  },
  {
    id: PaperlessCustomFieldDataType.String,
    name: $localize`Text`,
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
