import { Component, Input, inject } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { NgbActiveModal, NgbTypeaheadModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import {
  Observable,
  OperatorFunction,
  debounceTime,
  forkJoin,
  of,
  switchMap,
} from 'rxjs'
import { Document } from 'src/app/data/document'
import { EmailContact } from 'src/app/data/email-contact'
import { EmailTemplate } from 'src/app/data/email-template'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { EmailContactService } from 'src/app/services/rest/email-contact.service'
import { EmailTemplateService } from 'src/app/services/rest/email-template.service'
import { UserService } from 'src/app/services/rest/user.service'
import { ToastService } from 'src/app/services/toast.service'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

@Component({
  selector: 'pngx-email-document-dialog',
  templateUrl: './email-document-dialog.component.html',
  styleUrl: './email-document-dialog.component.scss',
  imports: [FormsModule, NgxBootstrapIconsModule, NgbTypeaheadModule],
})
export class EmailDocumentDialogComponent extends LoadingComponentWithPermissions {
  private activeModal = inject(NgbActiveModal)
  private documentService = inject(DocumentService)
  private toastService = inject(ToastService)
  private emailContactService = inject(EmailContactService)
  private emailTemplateService = inject(EmailTemplateService)
  private correspondentService = inject(CorrespondentService)
  private documentTypeService = inject(DocumentTypeService)
  private userService = inject(UserService)

  @Input()
  documentIds: number[]

  private _documents: Document[] = []

  @Input()
  set documents(value: Document[]) {
    this._documents = value
    if (value.length > 0) {
      this.buildPlaceholderContext(value[0])
    }
  }

  get documents(): Document[] {
    return this._documents
  }

  private placeholderContext: Record<string, string> = {}

  private _hasArchiveVersion: boolean = true

  @Input()
  set hasArchiveVersion(value: boolean) {
    this._hasArchiveVersion = value
    this.useArchiveVersion = value
  }

  get hasArchiveVersion(): boolean {
    return this._hasArchiveVersion
  }

  public useArchiveVersion: boolean = true

  // Recipient chips for To, CC, BCC
  public toRecipients: string[] = []
  public ccRecipients: string[] = []
  public bccRecipients: string[] = []

  // Input fields for typeahead
  public toInput: string = ''
  public ccInput: string = ''
  public bccInput: string = ''

  public showCcBcc: boolean = false

  public emailSubject: string = ''
  public emailMessage: string = ''

  public templates: EmailTemplate[] = []
  public allContacts: EmailContact[] = []
  public selectedTemplate: EmailTemplate | null = null

  constructor() {
    super()
    this.loading = false
    this.emailTemplateService
      .listAll()
      .subscribe((r) => (this.templates = r.results))
    this.emailContactService
      .listAll()
      .subscribe((r) => (this.allContacts = r.results))
  }

  private buildPlaceholderContext(doc: Document) {
    const created = doc.created ? new Date(doc.created) : null
    const added = doc.added ? new Date(doc.added) : null
    const ctx: Record<string, string> = {
      doc_title: doc.title ?? '',
      original_filename: doc.original_file_name?.replace(/\.[^.]+$/, '') ?? '',
      filename: doc.original_file_name?.replace(/\.[^.]+$/, '') ?? '',
      doc_url: doc.id
        ? `${window.location.origin}/documents/${doc.id}/details`
        : '',
      doc_id: doc.id ? String(doc.id) : '',
    }
    if (created) {
      ctx.created = created.toISOString().split('T')[0]
      ctx.created_year = String(created.getFullYear())
      ctx.created_year_short = String(created.getFullYear()).slice(-2)
      ctx.created_month = String(created.getMonth() + 1).padStart(2, '0')
      ctx.created_month_name = created.toLocaleDateString('en-US', {
        month: 'long',
      })
      ctx.created_month_name_short = created.toLocaleDateString('en-US', {
        month: 'short',
      })
      ctx.created_day = String(created.getDate()).padStart(2, '0')
      ctx.created_time = `${String(created.getHours()).padStart(2, '0')}:${String(created.getMinutes()).padStart(2, '0')}`
    }
    if (added) {
      ctx.added = added.toISOString()
      ctx.added_year = String(added.getFullYear())
      ctx.added_year_short = String(added.getFullYear()).slice(-2)
      ctx.added_month = String(added.getMonth() + 1).padStart(2, '0')
      ctx.added_month_name = added.toLocaleDateString('en-US', {
        month: 'long',
      })
      ctx.added_month_name_short = added.toLocaleDateString('en-US', {
        month: 'short',
      })
      ctx.added_day = String(added.getDate()).padStart(2, '0')
      ctx.added_time = `${String(added.getHours()).padStart(2, '0')}:${String(added.getMinutes()).padStart(2, '0')}`
    }
    // Resolve correspondent and document_type names
    const obs: Record<string, Observable<any>> = {}
    if (doc.correspondent) {
      obs['correspondent'] = this.correspondentService.getCached(
        doc.correspondent
      )
    }
    if (doc.document_type) {
      obs['document_type'] = this.documentTypeService.getCached(
        doc.document_type
      )
    }
    if (doc.owner) {
      obs['owner'] = this.userService.getCached(doc.owner)
    }
    if (Object.keys(obs).length > 0) {
      forkJoin(obs).subscribe((results: any) => {
        if (results.correspondent)
          ctx.correspondent = results.correspondent.name ?? ''
        if (results.document_type)
          ctx.document_type = results.document_type.name ?? ''
        if (results.owner) ctx.owner_username = results.owner.username ?? ''
        this.placeholderContext = ctx
      })
    } else {
      ctx.correspondent = ''
      ctx.document_type = ''
      ctx.owner_username = ''
      this.placeholderContext = ctx
    }
  }

  private renderPlaceholders(text: string): string {
    if (!text) return text
    return text.replace(/\{\{\s*(\w+)\s*\}\}/g, (match, key) => {
      return this.placeholderContext[key] ?? match
    })
  }

  private get allSelectedEmails(): string[] {
    return [...this.toRecipients, ...this.ccRecipients, ...this.bccRecipients]
  }

  public searchContacts: OperatorFunction<string, EmailContact[]> = (
    text$: Observable<string>
  ) =>
    text$.pipe(
      debounceTime(100),
      switchMap((term) => {
        const selected = this.allSelectedEmails
        const available = this.allContacts.filter(
          (c) => !selected.includes(c.email)
        )
        if (!term || term.length === 0) {
          return of(available.slice(0, 15))
        }
        const filtered = available.filter(
          (c) =>
            c.name?.toLowerCase().includes(term.toLowerCase()) ||
            c.email?.toLowerCase().includes(term.toLowerCase())
        )
        return of(filtered.slice(0, 15))
      })
    )

  public contactFormatter = (contact: EmailContact) =>
    `${contact.name} <${contact.email}>`

  public contactInputFormatter = (_contact: EmailContact) => ''

  public addRecipient(field: 'to' | 'cc' | 'bcc', event?: any) {
    let email: string
    if (event?.item) {
      event.preventDefault()
      email = event.item.email
    } else {
      email =
        field === 'to'
          ? this.toInput
          : field === 'cc'
            ? this.ccInput
            : this.bccInput
    }
    email = email?.trim()
    if (!email) return
    const list =
      field === 'to'
        ? this.toRecipients
        : field === 'cc'
          ? this.ccRecipients
          : this.bccRecipients
    if (!list.includes(email)) {
      list.push(email)
    }
    if (field === 'to') this.toInput = ''
    else if (field === 'cc') this.ccInput = ''
    else this.bccInput = ''
    // Re-focus input after selection (like tags closeOnSelect=false)
    setTimeout(() => {
      const inputId =
        field === 'to' ? 'toInput' : field === 'cc' ? 'ccInput' : 'bccInput'
      const el = document.getElementById(inputId) as HTMLInputElement
      if (el) {
        el.focus()
        el.dispatchEvent(new Event('input'))
      }
    })
  }

  public removeRecipient(field: 'to' | 'cc' | 'bcc', index: number) {
    const list =
      field === 'to'
        ? this.toRecipients
        : field === 'cc'
          ? this.ccRecipients
          : this.bccRecipients
    list.splice(index, 1)
  }

  public onInputKeydown(field: 'to' | 'cc' | 'bcc', event: KeyboardEvent) {
    if (
      event.key === 'Enter' ||
      event.key === ',' ||
      event.key === ';' ||
      event.key === 'Tab'
    ) {
      event.preventDefault()
      this.addRecipient(field)
    }
  }

  public onFocus(event: FocusEvent) {
    const input = event.target as HTMLInputElement
    input.dispatchEvent(new Event('input'))
  }

  public applyTemplate(template: EmailTemplate) {
    this.selectedTemplate = template
    this.emailSubject = this.renderPlaceholders(template.subject ?? '')
    this.emailMessage = this.renderPlaceholders(template.body ?? '')
    this.toastService.showInfo($localize`Template applied`)
  }

  public get canSend(): boolean {
    return (
      this.toRecipients.length > 0 &&
      this.emailSubject.length > 0 &&
      this.emailMessage.length > 0 &&
      !this.loading
    )
  }

  public emailDocuments() {
    this.loading = true
    const addresses = this.toRecipients.join(',')
    const cc = this.ccRecipients.join(',')
    const bcc = this.bccRecipients.join(',')
    this.documentService
      .emailDocuments(
        this.documentIds,
        addresses,
        this.emailSubject,
        this.emailMessage,
        this.useArchiveVersion,
        cc || undefined,
        bcc || undefined
      )
      .subscribe({
        next: () => {
          this.loading = false
          this.toRecipients = []
          this.ccRecipients = []
          this.bccRecipients = []
          this.emailSubject = ''
          this.emailMessage = ''
          this.selectedTemplate = null
          this.close()
          this.toastService.showInfo($localize`Email sent`)
        },
        error: (e) => {
          this.loading = false
          const errorMessage =
            this.documentIds.length > 1
              ? $localize`Error emailing documents`
              : $localize`Error emailing document`
          this.toastService.showError(errorMessage, e)
        },
      })
  }

  public close() {
    this.activeModal.close()
  }
}
