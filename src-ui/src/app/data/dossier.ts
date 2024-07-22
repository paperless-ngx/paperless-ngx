import { CustomFieldInstance } from './custom-field-instance';
import { MatchingModel } from './matching-model'
export enum DossierType {
    // just file tasks, for now
    Dossier = 'DOSSIER',
    Document = 'DOCUMENT',
  }
export interface Dossier extends MatchingModel {
    dossier_type?: DossierType;
    parent_dossier?: Dossier;
    parent_dossier_type?: Dossier;
    parent_dossier_type_name?: string;
    key?: string;
    url?: string;
    created?: Date;
    is_form: boolean;
    custom_fields?: CustomFieldInstance[];
}
