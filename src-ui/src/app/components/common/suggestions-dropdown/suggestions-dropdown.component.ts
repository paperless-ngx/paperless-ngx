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

  readonly appliedTags = input<number[]>([])
  readonly appliedCorrespondent = input<number>(null)
  readonly appliedDocumentType = input<number>(null)
  readonly appliedStoragePath = input<number>(null)

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

  get novelSuggestions(): number {
    return (
      (this.suggestions()?.suggested_correspondents?.length ?? 0) +
      (this.suggestions()?.suggested_tags?.length ?? 0) +
      (this.suggestions()?.suggested_document_types?.length ?? 0)
    )
  }

  get reusableSuggestions(): number {
    const correspondent = this.appliedCorrespondent()
    const documentType = this.appliedDocumentType()
    const storagePath = this.appliedStoragePath()
    // Storage paths count here but not in novelSuggestions: an existing one
    // can be applied from the field, a suggested name cannot create one.
    return (
      this.countUnapplied(this.suggestions()?.tags, this.appliedTags()) +
      this.countUnapplied(
        this.suggestions()?.correspondents,
        correspondent ? [correspondent] : []
      ) +
      this.countUnapplied(
        this.suggestions()?.document_types,
        documentType ? [documentType] : []
      ) +
      this.countUnapplied(
        this.suggestions()?.storage_paths,
        storagePath ? [storagePath] : []
      )
    )
  }

  get totalSuggestions(): number {
    return this.novelSuggestions + this.reusableSuggestions
  }

  private countUnapplied(suggested: number[], applied: number[]): number {
    return (suggested ?? []).filter((id) => !(applied ?? []).includes(id))
      .length
  }

  get noSuggestions(): boolean {
    const suggestions = this.suggestions()
    return (
      suggestions != null &&
      !suggestions.title &&
      !suggestions.tags?.length &&
      !suggestions.suggested_tags?.length &&
      !suggestions.correspondents?.length &&
      !suggestions.suggested_correspondents?.length &&
      !suggestions.document_types?.length &&
      !suggestions.suggested_document_types?.length &&
      !suggestions.storage_paths?.length &&
      !suggestions.suggested_storage_paths?.length &&
      !suggestions.dates?.length
    )
  }
}
