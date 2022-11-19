import { Component } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { first } from 'rxjs'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent'
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type'
import { PaperlessMailAccount } from 'src/app/data/paperless-mail-account'
import {
  MailAction,
  MailFilterAttachmentType,
  MailMetadataCorrespondentOption,
  MailMetadataTitleOption,
  PaperlessMailRule,
} from 'src/app/data/paperless-mail-rule'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { MailAccountService } from 'src/app/services/rest/mail-account.service'
import { MailRuleService } from 'src/app/services/rest/mail-rule.service'

@Component({
  selector: 'app-mail-rule-edit-dialog',
  templateUrl: './mail-rule-edit-dialog.component.html',
  styleUrls: ['./mail-rule-edit-dialog.component.scss'],
})
export class MailRuleEditDialogComponent extends EditDialogComponent<PaperlessMailRule> {
  accounts: PaperlessMailAccount[]
  correspondents: PaperlessCorrespondent[]
  documentTypes: PaperlessDocumentType[]

  constructor(
    service: MailRuleService,
    activeModal: NgbActiveModal,
    accountService: MailAccountService,
    correspondentService: CorrespondentService,
    documentTypeService: DocumentTypeService
  ) {
    super(service, activeModal)

    accountService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.accounts = result.results))

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
      assign_tags: new FormControl([]),
      assign_document_type: new FormControl(null),
      assign_correspondent_from: new FormControl(
        MailMetadataCorrespondentOption.FromNothing
      ),
      assign_correspondent: new FormControl(null),
    })
  }

  get showCorrespondentField(): boolean {
    return (
      this.objectForm?.get('assign_correspondent_from')?.value ==
      MailMetadataCorrespondentOption.FromCustom
    )
  }

  get attachmentTypeOptions() {
    return [
      {
        id: MailFilterAttachmentType.Attachments,
        name: $localize`Only process attachments.`,
      },
      {
        id: MailFilterAttachmentType.Everything,
        name: $localize`Process all files, including 'inline' attachments.`,
      },
    ]
  }

  get actionOptions() {
    return [
      {
        id: MailAction.Delete,
        name: $localize`Delete`,
      },
      {
        id: MailAction.Move,
        name: $localize`Move to specified folder`,
      },
      {
        id: MailAction.MarkRead,
        name: $localize`Mark as read, don't process read mails`,
      },
      {
        id: MailAction.Flag,
        name: $localize`Flag the mail, don't process flagged mails`,
      },
      {
        id: MailAction.Tag,
        name: $localize`Tag the mail with specified tag, don't process tagged mails`,
      },
    ]
  }

  get metadataTitleOptions() {
    return [
      {
        id: MailMetadataTitleOption.FromSubject,
        name: $localize`Use subject as title`,
      },
      {
        id: MailMetadataTitleOption.FromFilename,
        name: $localize`Use attachment filename as title`,
      },
    ]
  }

  get metadataCorrespondentOptions() {
    return [
      {
        id: MailMetadataCorrespondentOption.FromNothing,
        name: $localize`Do not assign a correspondent`,
      },
      {
        id: MailMetadataCorrespondentOption.FromEmail,
        name: $localize`Use mail address`,
      },
      {
        id: MailMetadataCorrespondentOption.FromName,
        name: $localize`Use name (or mail address if not available)`,
      },
      {
        id: MailMetadataCorrespondentOption.FromCustom,
        name: $localize`Use correspondent selected below`,
      },
    ]
  }
}
