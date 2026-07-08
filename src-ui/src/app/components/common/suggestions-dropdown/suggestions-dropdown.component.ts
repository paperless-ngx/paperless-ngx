import {
  Component,
  EventEmitter,
  Input,
  Output,
  ViewChild,
  signal,
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
  private suggestionsSignal = signal<DocumentSuggestions>(null)
  private aiEnabledSignal = signal(false)
  private loadingSignal = signal(false)
  private disabledSignal = signal(false)

  @Input()
  get suggestions(): DocumentSuggestions {
    return this.suggestionsSignal()
  }

  set suggestions(suggestions: DocumentSuggestions) {
    this.suggestionsSignal.set(suggestions)
  }

  @Input()
  get aiEnabled(): boolean {
    return this.aiEnabledSignal()
  }

  set aiEnabled(aiEnabled: boolean) {
    this.aiEnabledSignal.set(aiEnabled)
  }

  @Input()
  get loading(): boolean {
    return this.loadingSignal()
  }

  set loading(loading: boolean) {
    this.loadingSignal.set(loading)
  }

  @Input()
  get disabled(): boolean {
    return this.disabledSignal()
  }

  set disabled(disabled: boolean) {
    this.disabledSignal.set(disabled)
  }

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
      this.disabled ||
      this.loading ||
      (this.suggestions && !this.aiEnabled)
    ) {
      return
    }

    if (!this.suggestions) {
      this.getSuggestions.emit(this)
    } else {
      this.dropdown?.toggle()
    }
  }

  get totalSuggestions(): number {
    return (
      this.suggestions?.suggested_correspondents?.length +
        this.suggestions?.suggested_tags?.length +
        this.suggestions?.suggested_document_types?.length || 0
    )
  }
}
