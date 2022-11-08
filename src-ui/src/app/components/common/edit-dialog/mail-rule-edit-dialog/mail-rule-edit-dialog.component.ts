import { Component } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { first } from 'rxjs'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent'
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type'
import {
  MailAction,
  MailActionOptions,
  MailFilterAttachmentType,
  MailFilterAttachmentTypeOptions,
  MailMetadataCorrespondentOption,
  MailMetadataCorrespondentOptionOptions,
  MailMetadataTitleOption,
  MailMetadataTitleOptionOptions,
  PaperlessMailRule,
} from 'src/app/data/paperless-mail-rule'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { MailRuleService } from 'src/app/services/rest/mail-rule.service'

@Component({
  selector: 'app-mail-rule-edit-dialog',
  templateUrl: './mail-rule-edit-dialog.component.html',
  styleUrls: ['./mail-rule-edit-dialog.component.scss'],
})
export class MailRuleEditDialogComponent extends EditDialogComponent<PaperlessMailRule> {
  correspondents: PaperlessCorrespondent[]
  documentTypes: PaperlessDocumentType[]

  constructor(
    service: MailRuleService,
    activeModal: NgbActiveModal,
    correspondentService: CorrespondentService,
    documentTypeService: DocumentTypeService
  ) {
    super(service, activeModal)

    correspondentService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.correspondents = result.results))

    documentTypeService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.documentTypes = result.results))
  }

  getCreateTitle() {
    return $localize`Create new mail rule`
  }

  getEditTitle() {
    return $localize`Edit mail rule`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(null),
      order: new FormControl(null),
      account: new FormControl(null),
      folder: new FormControl('INBOX'),
      filter_from: new FormControl(null),
      filter_subject: new FormControl(null),
      filter_body: new FormControl(null),
      filter_attachment_filename: new FormControl(null),
      maximum_age: new FormControl(null),
      attachment_type: new FormControl(MailFilterAttachmentType.Attachments),
      action: new FormControl(MailAction.MarkRead),
      action_parameter: new FormControl(null),
      assign_title_from: new FormControl(MailMetadataTitleOption.FromSubject),
      assign_tags: new FormControl(null),
      assign_document_type: new FormControl(null),
      assign_correspondent_from: new FormControl(
        MailMetadataCorrespondentOption.FromNothing
      ),
      assign_correspondent: new FormControl(null),
    })
  }

  get attachmentTypeOptions() {
    return MailFilterAttachmentTypeOptions
  }

  get actionOptions() {
    return MailActionOptions
  }

  get metadataTitleOptions() {
    return MailMetadataTitleOptionOptions
  }

  get metadataCorrespondentOptions() {
    return MailMetadataCorrespondentOptionOptions
  }
}
