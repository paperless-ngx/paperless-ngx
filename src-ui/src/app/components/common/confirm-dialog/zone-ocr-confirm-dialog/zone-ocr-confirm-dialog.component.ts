import { Component, OnInit, inject, signal } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { takeUntil } from 'rxjs'
import { OcrTemplate } from 'src/app/data/ocr-template'
import { OcrTemplateService } from 'src/app/services/rest/ocr-template.service'
import { SelectComponent } from '../../input/select/select.component'
import { ConfirmDialogComponent } from '../confirm-dialog.component'

@Component({
  selector: 'pngx-zone-ocr-confirm-dialog',
  templateUrl: './zone-ocr-confirm-dialog.component.html',
  imports: [FormsModule, SelectComponent],
})
export class ZoneOcrConfirmDialogComponent
  extends ConfirmDialogComponent
  implements OnInit
{
  private readonly ocrTemplateService = inject(OcrTemplateService)

  public readonly templates = signal<OcrTemplate[]>([])

  /** The template to run, or null for every template that matches. */
  template: number | null = null

  ngOnInit() {
    this.ocrTemplateService
      .listAll()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((r) => this.templates.set(r.results))
  }
}
