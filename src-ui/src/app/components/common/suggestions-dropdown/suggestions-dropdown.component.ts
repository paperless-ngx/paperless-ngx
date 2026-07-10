import {
  Component,
  EventEmitter,
  Output,
  ViewChild,
  input,
} from '@angular/core'
import { NgbDropdown, NgbDropdownModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { DocumentSuggestions } from 'src/app/data/document-suggestions'
import { pngxPopperOptions } from 'src/app/utils/popper-options'

@Component({
  selector: 'pngx-suggestions-dropdown',
  imports: [NgbDropdownModule, NgxBootstrapIconsModule],
  templateUrl: './suggestions-dropdown.component.html',
  styleUrl: './suggestions-dropdown.component.scss',
})
export class SuggestionsDropdownComponent {
  public popperOptions = pngxPopperOptions

  @ViewChild('dropdown') dropdown: NgbDropdown
  readonly suggestions = input<DocumentSuggestions>(null)
  readonly aiEnabled = input(false)
  readonly loading = input(false)
  readonly disabled = input(false)

  @Output()
  getSuggestions: EventEmitter<SuggestionsDropdownComponent> =
    new EventEmitter()

  @Output()
  addTag: EventEmitter<string> = new EventEmitter()

  @Output()
  addDocumentType: EventEmitter<string> = new EventEmitter()

  @Output()
  addCorrespondent: EventEmitter<string> = new EventEmitter()

  public clickSuggest(): void {
    if (
      this.disabled() ||
      this.loading() ||
      (this.suggestions() && !this.aiEnabled())
    ) {
      return
    }

    if (!this.suggestions()) {
      this.getSuggestions.emit(this)
    } else {
      this.dropdown?.toggle()
    }
  }

  get totalSuggestions(): number {
    return (
      this.suggestions()?.suggested_correspondents?.length +
        this.suggestions()?.suggested_tags?.length +
        this.suggestions()?.suggested_document_types?.length || 0
    )
  }
}
