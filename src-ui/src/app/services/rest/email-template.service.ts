import { Injectable } from '@angular/core'
import { EmailTemplate } from 'src/app/data/email-template'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class EmailTemplateService extends AbstractNameFilterService<EmailTemplate> {
  constructor() {
    super()
    this.resourceName = 'email_templates'
  }
}
