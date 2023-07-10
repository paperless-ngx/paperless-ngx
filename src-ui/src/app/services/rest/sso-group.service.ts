import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { AbstractNameFilterService } from './abstract-name-filter-service'
import { PaperlessSSOGroup } from '../../data/paperless-sso-group'

@Injectable({
  providedIn: 'root',
})
export class SsoGroupService extends AbstractNameFilterService<PaperlessSSOGroup> {
  constructor(http: HttpClient) {
    super(http, 'sso_groups')
  }
}
