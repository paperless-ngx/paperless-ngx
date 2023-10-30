import { HttpTestingController } from '@angular/common/http/testing'
import { Subscription } from 'rxjs'
import { TestBed } from '@angular/core/testing'
import { environment } from 'src/environments/environment'
import { commonAbstractPaperlessServiceTests } from './abstract-paperless-service.spec'
import { CustomFieldsService } from './custom-fields.service'

let httpTestingController: HttpTestingController
let service: CustomFieldsService
let subscription: Subscription
const endpoint = 'custom_fields'

// run common tests
commonAbstractPaperlessServiceTests(endpoint, CustomFieldsService)
