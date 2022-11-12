import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { PaperlessGroup } from 'src/app/data/paperless-group'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class GroupService extends AbstractNameFilterService<PaperlessGroup> {
  constructor(http: HttpClient) {
    super(http, 'groups')
  }
}
