import { CommonModule } from '@angular/common'
import {
  trigger,
  state,
  style,
  transition,
  animate,
} from '@angular/animations'
import {
  Component,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges,
  inject,
} from '@angular/core'
import { NgbCollapseModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject, of } from 'rxjs'
import { takeUntil, catchError } from 'rxjs/operators'
import {
  AISuggestion,
  AISuggestionStatus,
  AISuggestionType,
} from 'src/app/data/ai-suggestion'
import { Correspondent } from 'src/app/data/correspondent'
import { CustomField } from 'src/app/data/custom-field'
import { DocumentType } from 'src/app/data/document-type'
import { StoragePath } from 'src/app/data/storage-path'
import { Tag } from 'src/app/data/tag'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { TagService } from 'src/app/services/rest/tag.service'
import { ToastService } from 'src/app/services/toast.service'

@Component({
  selector: 'pngx-ai-suggestions-panel',
  standalone: true,
  templateUrl: './ai-suggestions-panel.component.html',
  styleUrls: ['./ai-suggestions-panel.component.scss'],
  imports: [
    CommonModule,
    NgbCollapseModule,
    NgxBootstrapIconsModule,
  ],
  animations: [
    trigger('slideIn', [
      transition(':enter', [
        style({ transform: 'translateY(-20px)', opacity: 0 }),
        animate('300ms ease-out', style({ transform: 'translateY(0)', opacity: 1 })),
      ]),
    ]),
    trigger('fadeInOut', [
      transition(':enter', [
        style({ opacity: 0, transform: 'scale(0.95)' }),
        animate('200ms ease-out', style({ opacity: 1, transform: 'scale(1)' })),
      ]),
      transition(':leave', [
        animate('200ms ease-in', style({ opacity: 0, transform: 'scale(0.95)' })),
      ]),
    ]),
  ],
})
export class AiSuggestionsPanelComponent implements OnChanges, OnDestroy {
  private tagService = inject(TagService)
  private correspondentService = inject(CorrespondentService)
  private documentTypeService = inject(DocumentTypeService)
  private storagePathService = inject(StoragePathService)
  private customFieldsService = inject(CustomFieldsService)
  private toastService = inject(ToastService)

  @Input()
  suggestions: AISuggestion[] = []

  @Input()
  disabled: boolean = false

  @Output()
  apply = new EventEmitter<AISuggestion>()

  @Output()
  reject = new EventEmitter<AISuggestion>()

  public isCollapsed = false
  public pendingSuggestions: AISuggestion[] = []
  public groupedSuggestions: Map<AISuggestionType, AISuggestion[]> = new Map()
  public appliedCount = 0
  public rejectedCount = 0

  private tags: Tag[] = []
  private correspondents: Correspondent[] = []
  private documentTypes: DocumentType[] = []
  private storagePaths: StoragePath[] = []
  private customFields: CustomField[] = []
  private destroy$ = new Subject<void>()

  public AISuggestionType = AISuggestionType
  public AISuggestionStatus = AISuggestionStatus

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['suggestions']) {
      this.processSuggestions()
      this.loadMetadata()
    }
  }

  private processSuggestions(): void {
    this.pendingSuggestions = this.suggestions.filter(
      (s) => s.status === AISuggestionStatus.Pending
    )
    this.appliedCount = this.suggestions.filter(
      (s) => s.status === AISuggestionStatus.Applied
    ).length
    this.rejectedCount = this.suggestions.filter(
      (s) => s.status === AISuggestionStatus.Rejected
    ).length

    // Group suggestions by type
    this.groupedSuggestions.clear()
    this.pendingSuggestions.forEach((suggestion) => {
      const group = this.groupedSuggestions.get(suggestion.type) || []
      group.push(suggestion)
      this.groupedSuggestions.set(suggestion.type, group)
    })
  }

  private loadMetadata(): void {
    // Load tags if needed
    const tagSuggestions = this.pendingSuggestions.filter(
      (s) => s.type === AISuggestionType.Tag
    )
    if (tagSuggestions.length > 0) {
      this.tagService
        .listAll()
        .pipe(
          takeUntil(this.destroy$),
          catchError((error) => {
            console.error('Failed to load tags:', error)
            return of({ results: [] })
          })
        )
        .subscribe((tags) => {
          this.tags = tags.results
          this.updateSuggestionLabels()
        })
    }

    // Load correspondents if needed
    const correspondentSuggestions = this.pendingSuggestions.filter(
      (s) => s.type === AISuggestionType.Correspondent
    )
    if (correspondentSuggestions.length > 0) {
      this.correspondentService
        .listAll()
        .pipe(
          takeUntil(this.destroy$),
          catchError((error) => {
            console.error('Failed to load correspondents:', error)
            return of({ results: [] })
          })
        )
        .subscribe((correspondents) => {
          this.correspondents = correspondents.results
          this.updateSuggestionLabels()
        })
    }

    // Load document types if needed
    const documentTypeSuggestions = this.pendingSuggestions.filter(
      (s) => s.type === AISuggestionType.DocumentType
    )
    if (documentTypeSuggestions.length > 0) {
      this.documentTypeService
        .listAll()
        .pipe(
          takeUntil(this.destroy$),
          catchError((error) => {
            console.error('Failed to load document types:', error)
            return of({ results: [] })
          })
        )
        .subscribe((documentTypes) => {
          this.documentTypes = documentTypes.results
          this.updateSuggestionLabels()
        })
    }

    // Load storage paths if needed
    const storagePathSuggestions = this.pendingSuggestions.filter(
      (s) => s.type === AISuggestionType.StoragePath
    )
    if (storagePathSuggestions.length > 0) {
      this.storagePathService
        .listAll()
        .pipe(
          takeUntil(this.destroy$),
          catchError((error) => {
            console.error('Failed to load storage paths:', error)
            return of({ results: [] })
          })
        )
        .subscribe((storagePaths) => {
          this.storagePaths = storagePaths.results
          this.updateSuggestionLabels()
        })
    }

    // Load custom fields if needed
    const customFieldSuggestions = this.pendingSuggestions.filter(
      (s) => s.type === AISuggestionType.CustomField
    )
    if (customFieldSuggestions.length > 0) {
      this.customFieldsService
        .listAll()
        .pipe(
          takeUntil(this.destroy$),
          catchError((error) => {
            console.error('Failed to load custom fields:', error)
            return of({ results: [] })
          })
        )
        .subscribe((customFields) => {
          this.customFields = customFields.results
          this.updateSuggestionLabels()
        })
    }
  }

  private updateSuggestionLabels(): void {
    this.pendingSuggestions.forEach((suggestion) => {
      if (!suggestion.label) {
        suggestion.label = this.getLabel(suggestion)
      }
    })
  }

  public getLabel(suggestion: AISuggestion): string {
    if (suggestion.label) {
      return suggestion.label
    }

    switch (suggestion.type) {
      case AISuggestionType.Tag:
        const tag = this.tags.find((t) => t.id === suggestion.value)
        return tag ? tag.name : `Tag #${suggestion.value}`

      case AISuggestionType.Correspondent:
        const correspondent = this.correspondents.find(
          (c) => c.id === suggestion.value
        )
        return correspondent
          ? correspondent.name
          : `Correspondent #${suggestion.value}`

      case AISuggestionType.DocumentType:
        const docType = this.documentTypes.find(
          (dt) => dt.id === suggestion.value
        )
        return docType ? docType.name : `Document Type #${suggestion.value}`

      case AISuggestionType.StoragePath:
        const storagePath = this.storagePaths.find(
          (sp) => sp.id === suggestion.value
        )
        return storagePath ? storagePath.name : `Storage Path #${suggestion.value}`

      case AISuggestionType.CustomField:
        return suggestion.field_name || 'Custom Field'

      case AISuggestionType.Date:
        return new Date(suggestion.value).toLocaleDateString()

      case AISuggestionType.Title:
        return String(suggestion.value)

      default:
        return String(suggestion.value)
    }
  }

  public getTypeLabel(type: AISuggestionType): string {
    switch (type) {
      case AISuggestionType.Tag:
        return $localize`Tags`
      case AISuggestionType.Correspondent:
        return $localize`Correspondent`
      case AISuggestionType.DocumentType:
        return $localize`Document Type`
      case AISuggestionType.StoragePath:
        return $localize`Storage Path`
      case AISuggestionType.CustomField:
        return $localize`Custom Field`
      case AISuggestionType.Date:
        return $localize`Date`
      case AISuggestionType.Title:
        return $localize`Title`
      default:
        return String(type)
    }
  }

  public getTypeIcon(type: AISuggestionType): string {
    switch (type) {
      case AISuggestionType.Tag:
        return 'tag'
      case AISuggestionType.Correspondent:
        return 'person'
      case AISuggestionType.DocumentType:
        return 'file-earmark-text'
      case AISuggestionType.StoragePath:
        return 'folder'
      case AISuggestionType.CustomField:
        return 'input-cursor-text'
      case AISuggestionType.Date:
        return 'calendar'
      case AISuggestionType.Title:
        return 'pencil'
      default:
        return 'lightbulb'
    }
  }

  public getConfidenceClass(confidence: number): string {
    if (confidence >= 0.8) {
      return 'confidence-high'
    } else if (confidence >= 0.6) {
      return 'confidence-medium'
    } else {
      return 'confidence-low'
    }
  }

  public getConfidenceLabel(confidence: number): string {
    const percentage = Math.round(confidence * 100)
    if (confidence >= 0.8) {
      return $localize`High (${percentage}%)`
    } else if (confidence >= 0.6) {
      return $localize`Medium (${percentage}%)`
    } else {
      return $localize`Low (${percentage}%)`
    }
  }

  public getConfidenceIcon(confidence: number): string {
    if (confidence >= 0.8) {
      return 'check-circle-fill'
    } else if (confidence >= 0.6) {
      return 'exclamation-circle'
    } else {
      return 'question-circle'
    }
  }

  public applySuggestion(suggestion: AISuggestion): void {
    if (this.disabled) {
      return
    }

    suggestion.status = AISuggestionStatus.Applied
    this.apply.emit(suggestion)
    this.processSuggestions()

    this.toastService.showInfo(
      $localize`Applied AI suggestion: ${this.getLabel(suggestion)}`
    )
  }

  public rejectSuggestion(suggestion: AISuggestion): void {
    if (this.disabled) {
      return
    }

    suggestion.status = AISuggestionStatus.Rejected
    this.reject.emit(suggestion)
    this.processSuggestions()

    this.toastService.showInfo(
      $localize`Rejected AI suggestion: ${this.getLabel(suggestion)}`
    )
  }

  public applyAll(): void {
    if (this.disabled) {
      return
    }

    const count = this.pendingSuggestions.length
    this.pendingSuggestions.forEach((suggestion) => {
      suggestion.status = AISuggestionStatus.Applied
      this.apply.emit(suggestion)
    })
    this.processSuggestions()

    this.toastService.showInfo(
      $localize`Applied ${count} AI suggestions`
    )
  }

  public rejectAll(): void {
    if (this.disabled) {
      return
    }

    const count = this.pendingSuggestions.length
    this.pendingSuggestions.forEach((suggestion) => {
      suggestion.status = AISuggestionStatus.Rejected
      this.reject.emit(suggestion)
    })
    this.processSuggestions()

    this.toastService.showInfo(
      $localize`Rejected ${count} AI suggestions`
    )
  }

  public toggleCollapse(): void {
    this.isCollapsed = !this.isCollapsed
  }

  public get hasSuggestions(): boolean {
    return this.pendingSuggestions.length > 0
  }

  public get suggestionTypes(): AISuggestionType[] {
    return Array.from(this.groupedSuggestions.keys())
  }

  ngOnDestroy(): void {
    this.destroy$.next()
    this.destroy$.complete()
  }
}
