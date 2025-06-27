import { Injectable } from '@angular/core'
import { Correspondent } from 'src/app/data/correspondent'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class CorrespondentService extends AbstractNameFilterService<Correspondent> {
  constructor() {
    super()
    this.resourceName = 'correspondents'
  }
}
