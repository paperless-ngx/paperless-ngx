import { Component, forwardRef } from '@angular/core';
import { NG_VALUE_ACCESSOR } from '@angular/forms';
import { FILTER_ASN_ISNULL } from 'src/app/data/filter-rule-type';
import { DocumentService } from 'src/app/services/rest/document.service';
import { AbstractInputComponent } from '../abstract-input';

@Component({
  providers: [{
    provide: NG_VALUE_ACCESSOR,
    useExisting: forwardRef(() => NumberComponent),
    multi: true
  }],
  selector: 'app-input-number',
  templateUrl: './number.component.html',
  styleUrls: ['./number.component.scss']
})
export class NumberComponent extends AbstractInputComponent<number> {

  constructor(private documentService: DocumentService) {
    super()
  }

  nextAsn() {
    if (this.value) {
      return
    }
    this.documentService.listFiltered(1, 1, "archive_serial_number", true, [{rule_type: FILTER_ASN_ISNULL, value: "false"}]).subscribe(
      results => {
        if (results.count > 0) {
          this.value = results.results[0].archive_serial_number + 1
        } else {
          this.value = 1
        }
        this.onChange(this.value)
      }
    )
  }

}
