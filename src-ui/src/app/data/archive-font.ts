import { MatchingModel } from './matching-model'
import { Observable } from 'rxjs'
import { Tag } from './tag'
import { FontLanguage } from './font-language'

export interface ArchiveFont extends MatchingModel {
    first_upload?: Date
    last_upload?: Date
    languages?: number[]
    languages$?: Observable<FontLanguage[]>
    note?: string
}
