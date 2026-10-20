import { Component, OnInit, inject, signal } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { NgbDropdownModule, NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { firstValueFrom, takeUntil, tap } from 'rxjs'
import { DocumentType } from 'src/app/data/document-type'
import { OcrTemplate } from 'src/app/data/ocr-template'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { DirtyFormGuard } from 'src/app/guards/dirty-form.guard'
import { PermissionsService } from 'src/app/services/permissions.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { OcrTemplateService } from 'src/app/services/rest/ocr-template.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'
import { OcrTemplateEditorComponent } from './ocr-template-editor/ocr-template-editor.component'

@Component({
  selector: 'pngx-ocr-templates',
  templateUrl: './ocr-templates.component.html',
  imports: [
    PageHeaderComponent,
    IfPermissionsDirective,
    FormsModule,
    NgbDropdownModule,
    NgxBootstrapIconsModule,
  ],
})
export class OcrTemplatesComponent
  extends LoadingComponentWithPermissions
  implements OnInit
{
  private readonly ocrTemplateService = inject(OcrTemplateService)
  private readonly documentTypeService = inject(DocumentTypeService)
  public readonly permissionsService = inject(PermissionsService)
  private readonly modalService = inject(NgbModal)
  private readonly dirtyFormGuard = inject(DirtyFormGuard)
  private readonly toastService = inject(ToastService)

  public readonly templates = signal<OcrTemplate[]>([])
  private readonly documentTypes = signal<DocumentType[]>([])

  ngOnInit() {
    this.documentTypeService
      .listAll()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((r) => this.documentTypes.set(r.results))
    this.reload()
  }

  reload() {
    this.loading.set(true)
    this.ocrTemplateService
      .listAll()
      .pipe(
        takeUntil(this.unsubscribeNotifier),
        tap((r) => this.templates.set(r.results))
      )
      .subscribe(() => {
        this.show.set(true)
        this.loading.set(false)
      })
  }

  getDocumentTypeName(template: OcrTemplate): string {
    return (
      this.documentTypes().find((dt) => dt.id === template.document_type)
        ?.name ?? ''
    )
  }

  editTemplate(template?: OcrTemplate) {
    const modal = this.modalService.open(OcrTemplateEditorComponent, {
      backdrop: 'static',
      keyboard: false,
      size: 'xxl',
      fullscreen: 'lg',
      scrollable: true,
      ariaLabelledBy: 'ocr-template-editor-title',
      beforeDismiss: () => {
        const editor: OcrTemplateEditorComponent = modal.componentInstance
        if (editor.saving()) return false
        if (!editor.isDirty) return true
        return firstValueFrom(
          this.dirtyFormGuard.confirmChanges(undefined, $localize`Close`)
        )
      },
    })
    modal.componentInstance.object = template
    modal.componentInstance.succeeded
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((saved: OcrTemplate) => {
        this.toastService.showSuccess(
          $localize`Saved OCR template "${saved.name}".`
        )
        this.ocrTemplateService.clearCache()
        this.reload()
      })
    modal.componentInstance.failed
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((e) => {
        this.toastService.showError($localize`Error saving OCR template.`, e)
      })
  }

  toggleTemplateEnabled(template: OcrTemplate) {
    this.ocrTemplateService
      .patch({ id: template.id, enabled: template.enabled } as OcrTemplate)
      .subscribe({
        next: () => {
          this.toastService.showSuccess(
            template.enabled
              ? $localize`Enabled OCR template "${template.name}"`
              : $localize`Disabled OCR template "${template.name}"`
          )
          this.reload()
        },
        error: (e) => {
          this.toastService.showError(
            $localize`Error toggling OCR template "${template.name}".`,
            e
          )
          this.reload()
        },
      })
  }

  deleteTemplate(template: OcrTemplate) {
    const modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm delete OCR template`
    modal.componentInstance.messageBold = $localize`This operation will permanently delete this OCR template.`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Proceed`
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.componentInstance.buttonsEnabled.set(false)
      this.ocrTemplateService.delete(template).subscribe({
        next: () => {
          modal.close()
          this.toastService.showSuccess(
            $localize`Deleted OCR template "${template.name}".`
          )
          this.ocrTemplateService.clearCache()
          this.reload()
        },
        error: (e) => {
          modal.componentInstance.buttonsEnabled.set(true)
          this.toastService.showError(
            $localize`Error deleting OCR template "${template.name}".`,
            e
          )
        },
      })
    })
  }
}
