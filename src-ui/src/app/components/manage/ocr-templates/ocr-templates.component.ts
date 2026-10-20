import { Component, OnInit, inject, signal } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { NgbDropdownModule, NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { delay, firstValueFrom, takeUntil, tap } from 'rxjs'
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
  private readonly service = inject(OcrTemplateService)
  private readonly documentTypeService = inject(DocumentTypeService)
  private readonly modalService = inject(NgbModal)
  private readonly dirtyFormGuard = inject(DirtyFormGuard)
  private readonly toastService = inject(ToastService)
  permissionsService = inject(PermissionsService)

  readonly templates = signal<OcrTemplate[]>([])
  private readonly documentTypeNames = signal(new Map<number, string>())

  ngOnInit() {
    this.documentTypeService
      .listAll()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((r) => {
        this.documentTypeNames.set(
          new Map(r.results.map((dt) => [dt.id, dt.name]))
        )
      })
    this.reload()
  }

  reload() {
    this.loading.set(true)
    this.service
      .listAll()
      .pipe(
        takeUntil(this.unsubscribeNotifier),
        tap((r) => this.templates.set(r.results)),
        delay(100)
      )
      .subscribe(() => {
        this.show.set(true)
        this.loading.set(false)
      })
  }

  getDocumentTypeName(t: OcrTemplate): string {
    return (
      this.documentTypeNames().get(t.document_type) ??
      `${t.document_type ?? ''}`
    )
  }

  createTemplate() {
    this.editTemplate()
  }

  editTemplate(t?: OcrTemplate) {
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
        return editor.isDirty
          ? firstValueFrom(this.dirtyFormGuard.confirmChanges())
          : true
      },
    })
    modal.componentInstance.object = t
    modal.componentInstance.succeeded
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => this.reload())
  }

  toggleTemplate(t: OcrTemplate, enabled: boolean) {
    this.templates.update((templates) =>
      templates.map((template) =>
        template.id === t.id ? { ...template, enabled } : template
      )
    )
    this.service.patch({ ...t, enabled }).subscribe({
      error: (error) => {
        this.templates.update((templates) =>
          templates.map((template) =>
            template.id === t.id
              ? { ...template, enabled: t.enabled }
              : template
          )
        )
        this.toastService.showError(
          $localize`Error updating OCR template.`,
          error
        )
      },
    })
  }

  deleteTemplate(t: OcrTemplate) {
    const modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Delete OCR Template`
    modal.componentInstance.messageBold = t.name
    modal.componentInstance.message = $localize`Do you really want to delete this OCR template?`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Delete`
    modal.componentInstance.confirmClicked
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        modal.componentInstance.buttonsEnabled.set(false)
        this.service
          .delete(t)
          .pipe(takeUntil(this.unsubscribeNotifier))
          .subscribe({
            next: () => {
              modal.close()
              this.reload()
            },
            error: (error) => {
              modal.componentInstance.buttonsEnabled.set(true)
              this.toastService.showError(
                $localize`Error deleting OCR template.`,
                error
              )
            },
          })
      })
  }
}
