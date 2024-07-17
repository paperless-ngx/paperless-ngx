import { Document } from './document'
import { Folder } from './folder';
import { MatchingModel } from './matching-model'

export interface FolderDocument {
    documents: Document[];
    folders: Folder[];

}
