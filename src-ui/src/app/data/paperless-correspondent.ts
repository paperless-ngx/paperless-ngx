import { MatchingModel } from './matching-model';

export interface PaperlessCorrespondent extends MatchingModel {

  document_count?: number
  
  last_correspondence?: Date

}
