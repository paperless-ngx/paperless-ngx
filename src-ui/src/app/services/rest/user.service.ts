import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { PaperlessUser } from 'src/app/data/paperless-user'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class UserService extends AbstractNameFilterService<PaperlessUser> {
  constructor(http: HttpClient) {
    super(http, 'users')
  }
}
