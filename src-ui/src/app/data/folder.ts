import { MatchingModel } from './matching-model'
import { Document } from './document'

export interface Folder extends MatchingModel {
    documentCount?: number;
    childFolderCount?: number;
    filesize?: number;
    path: string;
    checksum: string;
    parentFolder: number | null;
    owner: number;
    type: string;
    document?: Document;
  modified?: Date;

}
