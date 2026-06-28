import { Component, OnInit, inject } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { Router } from '@angular/router'
import { NgbDropdownModule, NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { delay, takeUntil, tap } from 'rxjs'
import { OcrTemplate } from 'src/app/data/ocr-template'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { PermissionsService } from 'src/app/services/permissions.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { OcrTemplateService } from 'src/app/services/rest/ocr-template.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

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
  private readonly router = inject(Router)
  private readonly modalService = inject(NgbModal)
  private readonly toastService = inject(ToastService)
  permissionsService = inject(PermissionsService)

  public templates: OcrTemplate[] = []
  private documentTypeNames: Map<number, string> = new Map()

  ngOnInit() {
    this.documentTypeService
      .listAll()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((r) => {
        this.documentTypeNames = new Map(
          r.results.map((dt) => [dt.id, dt.name])
        )
      })
    this.reload()
  }

  reload() {
    this.loading = true
    this.service
      .listAll()
      .pipe(
        takeUntil(this.unsubscribeNotifier),
        tap((r) => (this.templates = r.results)),
        delay(100)
      )
      .subscribe(() => {
        this.show = true
        this.loading = false
      })
  }

  getDocumentTypeName(t: OcrTemplate): string {
    return (
      this.documentTypeNames.get(t.document_type) ?? `${t.document_type ?? ''}`
    )
  }

  createTemplate() {
    this.router.navigate(['/ocr-templates', 'new'])
  }

  editTemplate(t: OcrTemplate) {
    this.router.navigate(['/ocr-templates', t.id])
  }

  toggleTemplate(t: OcrTemplate) {
    // ngModel has already flipped t.enabled; restore it if persistence fails.
    const enabled = t.enabled
    this.service.patch(t).subscribe({
      error: (error) => {
        t.enabled = !enabled
        this.toastService.showError(
          $localize`Error updating OCR template.`,
          error
        )
      },
    })
  }

  deleteTemplate(t: OcrTemplate) {
    const modal = this.modalService.open(ConfirmDialogComponent)
    modal.componentInstance.title = $localize`Delete OCR Template`
    modal.componentInstance.messageBoldPart = t.name
    modal.componentInstance.message = $localize`Do you really want to delete this OCR template?`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Delete`
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.close()
      this.service.delete(t).subscribe(() => this.reload())
    })
  }
}
