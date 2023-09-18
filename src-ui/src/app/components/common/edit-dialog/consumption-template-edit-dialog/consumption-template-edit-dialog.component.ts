import { Component } from '@angular/core'
import { FormGroup, FormControl } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { first } from 'rxjs'
import {
  DocumentSource,
  PaperlessConsumptionTemplate,
} from 'src/app/data/paperless-consumption-template'
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent'
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type'
import { PaperlessStoragePath } from 'src/app/data/paperless-storage-path'
import { ConsumptionTemplateService } from 'src/app/services/rest/consumption-template.service'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { EditDialogComponent } from '../edit-dialog.component'
import { MailRuleService } from 'src/app/services/rest/mail-rule.service'
import { PaperlessMailRule } from 'src/app/data/paperless-mail-rule'

export const DOCUMENT_SOURCE_OPTIONS = [
  {
    id: DocumentSource.ConsumeFolder,
    name: $localize`Consume Folder`,
  },
  {
    id: DocumentSource.ApiUpload,
    name: $localize`API Upload`,
  },
  {
    id: DocumentSource.MailFetch,
    name: $localize`Mail Fetch`,
  },
]

@Component({
  selector: 'pngx-consumption-template-edit-dialog',
  templateUrl: './consumption-template-edit-dialog.component.html',
  styleUrls: ['./consumption-template-edit-dialog.component.scss'],
})
export class ConsumptionTemplateEditDialogComponent extends EditDialogComponent<PaperlessConsumptionTemplate> {
  templates: PaperlessConsumptionTemplate[]
  correspondents: PaperlessCorrespondent[]
  documentTypes: PaperlessDocumentType[]
  storagePaths: PaperlessStoragePath[]
  mailRules: PaperlessMailRule[]

  constructor(
    service: ConsumptionTemplateService,
    activeModal: NgbActiveModal,
    correspondentService: CorrespondentService,
    documentTypeService: DocumentTypeService,
    storagePathService: StoragePathService,
    mailRuleService: MailRuleService,
    userService: UserService,
    settingsService: SettingsService
  ) {
    super(service, activeModal, userService, settingsService)

    correspondentService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.correspondents = result.results))

    documentTypeService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.documentTypes = result.results))

    storagePathService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.storagePaths = result.results))

    mailRuleService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.mailRules = result.results))
  }

  getCreateTitle() {
    return $localize`Create new consumption template`
  }

  getEditTitle() {
    return $localize`Edit consumption template`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(null),
      account: new FormControl(null),
      filter_filename: new FormControl(null),
      filter_path: new FormControl(null),
      filter_mailrule: new FormControl(null),
      order: new FormControl(null),
      sources: new FormControl([]),
      assign_title: new FormControl(null),
      assign_tags: new FormControl([]),
      assign_owner: new FormControl(null),
      assign_document_type: new FormControl(null),
      assign_correspondent: new FormControl(null),
      assign_storage_path: new FormControl(null),
      assign_view_users: new FormControl([]),
      assign_view_groups: new FormControl([]),
      assign_change_users: new FormControl([]),
      assign_change_groups: new FormControl([]),
    })
  }

  get sourceOptions() {
    return DOCUMENT_SOURCE_OPTIONS
  }
}
