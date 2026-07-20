import { Injectable } from '@angular/core'
import { NamedCounter } from 'src/app/data/named-counter'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class NamedCounterService extends AbstractNameFilterService<NamedCounter> {
  constructor() {
    super()
    this.resourceName = 'named_counters'
  }
}
