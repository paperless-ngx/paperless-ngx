import { Component, OnInit, inject } from '@angular/core'
import { Router } from '@angular/router'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { Subject, takeUntil } from 'rxjs'
import { OcrTemplate } from 'src/app/data/ocr-template'
import { OcrTemplateService } from 'src/app/services/rest/ocr-template.service'
import { CommonModule } from '@angular/common'
import { RouterModule } from '@angular/router'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'

@Component({
  selector: 'pngx-ocr-templates',
  standalone: true,
  imports: [CommonModule, RouterModule, NgxBootstrapIconsModule],
  templateUrl: './ocr-templates.component.html',
})
export class OcrTemplatesComponent implements OnInit {
  private readonly service = inject(OcrTemplateService)
  private readonly router = inject(Router)
  private readonly modalService = inject(NgbModal)
  private readonly destroy$ = new Subject<void>()

  templates: OcrTemplate[] = []
  loading = true

  ngOnInit() {
    this.reload()
  }

  reload() {
    this.loading = true
    this.service.listAll().pipe(takeUntil(this.destroy$)).subscribe({
      next: (results) => {
        this.templates = results.results
        this.loading = false
      },
      error: () => {
        this.loading = false
      },
    })
  }

  createTemplate() {
    this.router.navigate(['/ocr-templates', 'new'])
  }

  editTemplate(t: OcrTemplate) {
    this.router.navigate(['/ocr-templates', t.id])
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

  toggleTemplate(t: OcrTemplate) {
    t.enabled = !t.enabled
    this.service.patch(t).subscribe(() => this.reload())
  }

  ngOnDestroy() {
    this.destroy$.next()
    this.destroy$.complete()
  }
}
