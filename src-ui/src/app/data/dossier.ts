import { CustomFieldInstance } from './custom-field-instance';
import { MatchingModel } from './matching-model'
export enum DossierType {
    // just file tasks, for now
    Dossier = 'DOSSIER',
    Document = 'DOCUMENT',
    File = 'FILE',
  }
export interface Dossier extends MatchingModel {
    type?: DossierType;
    parent_dossier?: Dossier;
    dossier_form?: Dossier;
    dossier_form_name?: string;
    document_matching?: number;
    key?: string;
    url?: string;
    created?: Date;
    custom_fields?: CustomFieldInstance[];
}
