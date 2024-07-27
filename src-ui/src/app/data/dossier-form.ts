import { CustomFieldInstance } from './custom-field-instance';
import { MatchingModel } from './matching-model'
export enum DossierType {
    // just file tasks, for now
    Dossier = 'DOSSIER',
    Document = 'DOCUMENT',
  }
export interface DossierForm extends MatchingModel {
    type?: DossierType;
    // key?: string;
    username?: string;
    password?: string;
    url?: string;
    form_rule?: string;
    created?: Date;
    custom_fields?: CustomFieldInstance[];
}
