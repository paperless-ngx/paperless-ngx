import { CommonModule } from '@angular/common'
import { Component, EventEmitter, OnInit, Output, inject } from '@angular/core'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { first } from 'rxjs'
import { CustomField } from 'src/app/data/custom-field'
import {
  CSV_EXPORT_CUSTOM_FIELDS_STORAGE_KEY,
  CSV_EXPORT_FIELDS_STORAGE_KEY,
  DEFAULT_CSV_EXPORT_FIELDS,
  EXPORT_DOCUMENT_FIELDS,
} from 'src/app/data/document'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import {
  DocumentSelectionQuery,
  DocumentService,
} from 'src/app/services/rest/document.service'
import { SettingsService } from 'src/app/services/settings.service'

@Component({
  selector: 'pngx-export-csv-dialog',
  templateUrl: './export-csv-dialog.component.html',
  styleUrl: './export-csv-dialog.component.scss',
  imports: [CommonModule],
})
export class ExportCsvDialogComponent implements OnInit {
  private activeModal = inject(NgbActiveModal)
  private documentService = inject(DocumentService)
  private customFieldService = inject(CustomFieldsService)
  private permissionsService = inject(PermissionsService)
  private settingsService = inject(SettingsService)

  @Output()
  succeeded = new EventEmitter<Blob>()

  @Output()
  failed = new EventEmitter<any>()

  selection: DocumentSelectionQuery
  selectionCount?: number

  documentFields: Array<{ id: string; name: string }> = []
  customFields: CustomField[] = []
  selectedDocumentFields = new Set<string>()
  selectedCustomFields = new Set<number>()
  exporting = false

  ngOnInit(): void {
    this.documentFields = this.getAvailableDocumentFields()
    this.loadSavedSelection()

    if (
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.CustomField
      )
    ) {
      this.customFieldService
        .listAll()
        .pipe(first())
        .subscribe((result) => {
          this.customFields = result.results
          this.loadSavedCustomFieldSelection()
        })
    }
  }

  get hasSelection(): boolean {
    return (
      this.selectedDocumentFields.size > 0 || this.selectedCustomFields.size > 0
    )
  }

  private getAvailableDocumentFields(): Array<{ id: string; name: string }> {
    return EXPORT_DOCUMENT_FIELDS.filter((field) => {
      if (
        field.id === 'id' ||
        field.id === 'modified' ||
        field.id === 'mime_type' ||
        field.id === 'filename' ||
        field.id === 'archived_filename' ||
        field.id === 'content'
      ) {
        return true
      }

      if (
        field.id === 'note' &&
        !this.settingsService.get(SETTINGS_KEYS.NOTES_ENABLED)
      ) {
        return false
      }

      if (
        ['title', 'created', 'added', 'asn', 'pagecount', 'shared'].includes(
          field.id
        )
      ) {
        return true
      }

      let type: PermissionType = Object.values(PermissionType).find((t) =>
        t.includes(field.id)
      )
      if (field.id === 'owner') {
        type = PermissionType.User
      }

      return this.permissionsService.currentUserCan(PermissionAction.View, type)
    })
  }

  private loadSavedSelection(): void {
    const saved = localStorage.getItem(CSV_EXPORT_FIELDS_STORAGE_KEY)
    if (saved) {
      try {
        const parsed = JSON.parse(saved) as string[]
        const available = new Set(this.documentFields.map((field) => field.id))
        parsed
          .filter((field) => available.has(field))
          .forEach((field) => this.selectedDocumentFields.add(field))
      } catch {
        this.applyDefaultDocumentFields()
      }
    } else {
      this.applyDefaultDocumentFields()
    }
  }

  private loadSavedCustomFieldSelection(): void {
    const saved = localStorage.getItem(CSV_EXPORT_CUSTOM_FIELDS_STORAGE_KEY)
    if (saved) {
      try {
        const parsed = JSON.parse(saved) as number[]
        const available = new Set(this.customFields.map((field) => field.id))
        parsed
          .filter((fieldId) => available.has(fieldId))
          .forEach((fieldId) => this.selectedCustomFields.add(fieldId))
      } catch {
        // ignore invalid saved state
      }
    }
  }

  private applyDefaultDocumentFields(): void {
    const available = new Set(this.documentFields.map((field) => field.id))
    DEFAULT_CSV_EXPORT_FIELDS.filter((field) => available.has(field)).forEach(
      (field) => this.selectedDocumentFields.add(field)
    )
  }

  toggleDocumentField(fieldId: string): void {
    if (this.selectedDocumentFields.has(fieldId)) {
      this.selectedDocumentFields.delete(fieldId)
    } else {
      this.selectedDocumentFields.add(fieldId)
    }
  }

  toggleCustomField(fieldId: number): void {
    if (this.selectedCustomFields.has(fieldId)) {
      this.selectedCustomFields.delete(fieldId)
    } else {
      this.selectedCustomFields.add(fieldId)
    }
  }

  selectAllDocumentFields(): void {
    this.documentFields.forEach((field) =>
      this.selectedDocumentFields.add(field.id)
    )
  }

  selectNoDocumentFields(): void {
    this.selectedDocumentFields.clear()
  }

  selectAllCustomFields(): void {
    this.customFields.forEach((field) =>
      this.selectedCustomFields.add(field.id)
    )
  }

  selectNoCustomFields(): void {
    this.selectedCustomFields.clear()
  }

  private saveSelection(): void {
    localStorage.setItem(
      CSV_EXPORT_FIELDS_STORAGE_KEY,
      JSON.stringify(Array.from(this.selectedDocumentFields))
    )
    localStorage.setItem(
      CSV_EXPORT_CUSTOM_FIELDS_STORAGE_KEY,
      JSON.stringify(Array.from(this.selectedCustomFields))
    )
  }

  export(): void {
    if (!this.hasSelection) {
      return
    }

    this.exporting = true
    this.saveSelection()

    this.documentService
      .bulkExportCsv(
        this.selection,
        Array.from(this.selectedDocumentFields),
        Array.from(this.selectedCustomFields)
      )
      .pipe(first())
      .subscribe({
        next: (result) => {
          this.exporting = false
          this.succeeded.emit(result)
          this.activeModal.close()
        },
        error: (error) => {
          this.exporting = false
          this.failed.emit(error)
        },
      })
  }

  cancel(): void {
    this.activeModal.dismiss()
  }
}
