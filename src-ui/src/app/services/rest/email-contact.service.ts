import { Injectable } from '@angular/core'
import { EmailContact } from 'src/app/data/email-contact'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class EmailContactService extends AbstractNameFilterService<EmailContact> {
  constructor() {
    super()
    this.resourceName = 'email_contacts'
  }
}
