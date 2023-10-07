import { Component, forwardRef, Input } from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import { DocumentService } from 'src/app/services/rest/document.service'
import { AbstractInputComponent } from '../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => NumberComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-number',
  templateUrl: './number.component.html',
  styleUrls: ['./number.component.scss'],
})
export class NumberComponent extends AbstractInputComponent<number> {
  @Input()
  showAdd: boolean = true

  constructor(private documentService: DocumentService) {
    super()
  }

  nextAsn() {
    if (this.value) {
      return
    }
    this.documentService.getNextAsn().subscribe((nextAsn) => {
      this.value = nextAsn
      this.onChange(this.value)
    })
  }
}
