import { ObjectWithId } from './object-with-id'

export interface ContentType extends ObjectWithId {

    model?: string

    app_label?: string
}
