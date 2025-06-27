import { Component, inject } from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { first } from 'rxjs'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { Correspondent } from 'src/app/data/correspondent'
import { DocumentType } from 'src/app/data/document-type'
import { MailAccount } from 'src/app/data/mail-account'
import {
  MailAction,
  MailFilterAttachmentType,
  MailMetadataCorrespondentOption,
  MailMetadataTitleOption,
  MailRule,
  MailRuleConsumptionScope,
  MailRulePdfLayout,
} from 'src/app/data/mail-rule'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { MailAccountService } from 'src/app/services/rest/mail-account.service'
import { MailRuleService } from 'src/app/services/rest/mail-rule.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { CheckComponent } from '../../input/check/check.component'
import { NumberComponent } from '../../input/number/number.component'
import { SelectComponent } from '../../input/select/select.component'
import { SwitchComponent } from '../../input/switch/switch.component'
import { TagsComponent } from '../../input/tags/tags.component'
import { TextComponent } from '../../input/text/text.component'

const ATTACHMENT_TYPE_OPTIONS = [
  {
    id: MailFilterAttachmentType.Attachments,
    name: $localize`Only process attachments`,
  },
  {
    id: MailFilterAttachmentType.Everything,
    name: $localize`Process all files, including 'inline' attachments`,
  },
]

const CONSUMPTION_SCOPE_OPTIONS = [
  {
    id: MailRuleConsumptionScope.Attachments,
    name: $localize`Only process attachments`,
  },
  {
    id: MailRuleConsumptionScope.EmailOnly,
    name: $localize`Process message as .eml`,
  },
  {
    id: MailRuleConsumptionScope.Everything,
    name: $localize`Process message as .eml and attachments separately`,
  },
]

const PDF_LAYOUT_OPTIONS = [
  {
    id: MailRulePdfLayout.Default,
    name: $localize`System default`,
  },
  {
    id: MailRulePdfLayout.TextHtml,
    name: $localize`Text, then HTML`,
  },
  {
    id: MailRulePdfLayout.HtmlText,
    name: $localize`HTML, then text`,
  },
  {
    id: MailRulePdfLayout.HtmlOnly,
    name: $localize`HTML only`,
  },
  {
    id: MailRulePdfLayout.TextOnly,
    name: $localize`Text only`,
  },
]

const ACTION_OPTIONS = [
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

const METADATA_TITLE_OPTIONS = [
  {
    id: MailMetadataTitleOption.FromSubject,
    name: $localize`Use subject as title`,
  },
  {
    id: MailMetadataTitleOption.FromFilename,
    name: $localize`Use attachment filename as title`,
  },
  {
    id: MailMetadataTitleOption.None,
    name: $localize`Do not assign title from this rule`,
  },
]

const METADATA_CORRESPONDENT_OPTIONS = [
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

@Component({
  selector: 'pngx-mail-rule-edit-dialog',
  templateUrl: './mail-rule-edit-dialog.component.html',
  styleUrls: ['./mail-rule-edit-dialog.component.scss'],
  imports: [
    SelectComponent,
    TagsComponent,
    CheckComponent,
    TextComponent,
    NumberComponent,
    SwitchComponent,
    FormsModule,
    ReactiveFormsModule,
  ],
})
export class MailRuleEditDialogComponent extends EditDialogComponent<MailRule> {
  private accountService: MailAccountService
  private correspondentService: CorrespondentService
  private documentTypeService: DocumentTypeService

  accounts: MailAccount[]
  correspondents: Correspondent[]
  documentTypes: DocumentType[]

  constructor() {
    super()
    this.service = inject(MailRuleService)
    this.accountService = inject(MailAccountService)
    this.correspondentService = inject(CorrespondentService)
    this.documentTypeService = inject(DocumentTypeService)
    this.userService = inject(UserService)
    this.settingsService = inject(SettingsService)

    this.accountService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.accounts = result.results))

    this.correspondentService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.correspondents = result.results))

    this.documentTypeService
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
      enabled: new FormControl(true),
      folder: new FormControl('INBOX'),
      filter_from: new FormControl(null),
      filter_to: new FormControl(null),
      filter_subject: new FormControl(null),
      filter_body: new FormControl(null),
      filter_attachment_filename_include: new FormControl(null),
      filter_attachment_filename_exclude: new FormControl(null),
      maximum_age: new FormControl(null),
      attachment_type: new FormControl(MailFilterAttachmentType.Attachments),
      pdf_layout: new FormControl(MailRulePdfLayout.Default),
      consumption_scope: new FormControl(MailRuleConsumptionScope.Attachments),
      order: new FormControl(null),
      action: new FormControl(MailAction.MarkRead),
      action_parameter: new FormControl(null),
      assign_title_from: new FormControl(MailMetadataTitleOption.FromSubject),
      assign_tags: new FormControl([]),
      assign_document_type: new FormControl(null),
      assign_correspondent_from: new FormControl(
        MailMetadataCorrespondentOption.FromNothing
      ),
      assign_correspondent: new FormControl(null),
      assign_owner_from_rule: new FormControl(true),
    })
  }

  get showCorrespondentField(): boolean {
    return (
      this.objectForm?.get('assign_correspondent_from')?.value ==
      MailMetadataCorrespondentOption.FromCustom
    )
  }

  get showActionParamField(): boolean {
    return (
      this.objectForm?.get('action')?.value == MailAction.Move ||
      this.objectForm?.get('action')?.value == MailAction.Tag
    )
  }

  get attachmentTypeOptions() {
    return ATTACHMENT_TYPE_OPTIONS
  }

  get actionOptions() {
    return ACTION_OPTIONS
  }

  get metadataTitleOptions() {
    return METADATA_TITLE_OPTIONS
  }

  get metadataCorrespondentOptions() {
    return METADATA_CORRESPONDENT_OPTIONS
  }

  get consumptionScopeOptions() {
    return CONSUMPTION_SCOPE_OPTIONS
  }

  get pdfLayoutOptions() {
    return PDF_LAYOUT_OPTIONS
  }
}
