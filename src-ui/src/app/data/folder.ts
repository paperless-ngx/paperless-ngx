import { MatchingModel } from './matching-model'

export interface Folder extends MatchingModel {
    documentCount?: number;
    childFolderCount?: number;
    filesize?: number;
    path: string;
    checksum: string;
    parentFolder: number | null;
}
