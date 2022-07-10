import { Observable } from 'rxjs';
import { MatchingModel } from './matching-model';
import { PaperlessCategory } from './paperless-category';

export interface PaperlessCorrespondent extends MatchingModel {

  category$?: Observable<PaperlessCategory>

  category?: number

  last_correspondence?: Date

}
