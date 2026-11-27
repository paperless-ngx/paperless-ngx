import {
  ChangeDetectorRef,
  Component,
  EventEmitter,
  forwardRef,
  inject,
  Input,
  OnInit,
  Output,
  ViewChild,
} from '@angular/core'
import {
  ControlValueAccessor,
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { RouterModule } from '@angular/router'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectComponent, NgSelectModule } from '@ng-select/ng-select'
import { first, firstValueFrom, tap } from 'rxjs'
import { BootstrapIconComponent } from 'src/app/components/common/bootstrap-icon/bootstrap-icon.component'
import { Tag } from 'src/app/data/tag'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { TagService } from 'src/app/services/rest/tag.service'
import { SettingsService } from 'src/app/services/settings.service'
import { getTagAncestors, partitionTags } from 'src/app/utils/tag-display'
import { matchesSearchText } from 'src/app/utils/text-search'
import { ConfirmDialogComponent } from '../../confirm-dialog/confirm-dialog.component'
import { HiddenTagsBadgeComponent } from '../../hidden-tags-badge/hidden-tags-badge.component'
import { EditDialogMode } from '../../edit-dialog/edit-dialog.component'
import { TagEditDialogComponent } from '../../edit-dialog/tag-edit-dialog/tag-edit-dialog.component'
import { TagComponent } from '../../tag/tag.component'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => TagsComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-tags',
  templateUrl: './tags.component.html',
  styleUrls: ['./tags.component.scss'],
  imports: [
    TagComponent,
    NgSelectModule,
    FormsModule,
    ReactiveFormsModule,
    RouterModule,
    BootstrapIconComponent,
    HiddenTagsBadgeComponent,
  ],
})
export class TagsComponent implements OnInit, ControlValueAccessor {
  private tagService = inject(TagService)
  private modalService = inject(NgbModal)
  private readonly settingsService = inject(SettingsService)
  private readonly changeDetector = inject(ChangeDetectorRef)

  constructor() {
    this.createTagRef = this.createTag.bind(this)
  }

  onChange = (newValue: number[]) => {}

  onTouched = () => {}

  writeValue(newValue: number[]): void {
    this.value = newValue
    this.changeDetector.markForCheck()
  }
  registerOnChange(fn: any): void {
    this.onChange = fn
  }
  registerOnTouched(fn: any): void {
    this.onTouched = fn
  }
  setDisabledState?(isDisabled: boolean): void {
    this.disabled = isDisabled
    this.changeDetector.markForCheck()
  }

  ngOnInit(): void {
    this.tagService.listAll().subscribe((result) => {
      this.tags = result.results
      this.tagsLoaded = true
      this.changeDetector.markForCheck()
    })
  }

  @Input()
  title = $localize`Tags`

  @Input()
  disabled = false

  @Input()
  hint

  @Input()
  suggestions: number[]

  @Input()
  allowCreate: boolean = true

  @Input()
  hideAddButton: boolean = false

  @Input()
  showFilter: boolean = false

  @Input()
  horizontal: boolean = false

  @Input()
  multiple: boolean = true

  @Input()
  preserveHierarchy: boolean = true

  @Output()
  filterDocuments = new EventEmitter<Tag[]>()

  @ViewChild('tagSelect') select: NgSelectComponent

  value: number[] = []

  tags: Tag[] = []

  private tagsLoaded = false

  public createTagRef: (name) => void

  public searchFn = (term: string, tag: Tag): boolean =>
    matchesSearchText(
      [this.getParentChain(tag?.id).map((parent) => parent.name), tag?.name]
        .flat()
        .join(' '),
      term
    )

  /**
   * Selected tags that are ancestors of another selected tag which are shown
   * as segments of their descendant's badge.
   */
  isImplied(id: number): boolean {
    return !!this.value?.includes(id) && !this.display.shown.has(id)
  }

  private get showsHierarchy(): boolean {
    return (
      this.preserveHierarchy &&
      !!this.settingsService.get(SETTINGS_KEYS.TAGS_SHOW_HIERARCHY)
    )
  }

  isHidden(id: number): boolean {
    return this.display.hiddenSet.has(id)
  }

  /**
   * Tags that are hidden from the current user.
   */
  get hiddenTagIds(): number[] {
    return this.display.hidden
  }

  private displayCache: {
    value: number[]
    tagsById: Map<number, Tag>
    showsHierarchy: boolean
    tagsLoaded: boolean
    shown: Set<number>
    hidden: number[]
    hiddenSet: Set<number>
  }

  /**
   * Partition of the current value, recomputed only when the value, tags or
   * hierarchy setting change.
   */
  private get display() {
    const tagsById = this.tagsById
    const showsHierarchy = this.showsHierarchy
    const cached = this.displayCache
    if (
      cached?.value === this.value &&
      cached.tagsById === tagsById &&
      cached.showsHierarchy === showsHierarchy &&
      cached.tagsLoaded === this.tagsLoaded
    ) {
      return cached
    }
    const { visible, hidden } = partitionTags(
      this.value,
      tagsById,
      showsHierarchy
    )
    const hiddenIds = this.tagsLoaded ? hidden : []
    this.displayCache = {
      value: this.value,
      tagsById,
      showsHierarchy,
      tagsLoaded: this.tagsLoaded,
      shown: new Set([...visible, ...hidden]),
      hidden: hiddenIds,
      hiddenSet: new Set(hiddenIds),
    }
    return this.displayCache
  }

  /**
   * Remove the last visible tag (in case its actually a hidden ancestor or a
   * tag the user cannot view)
   */
  readonly onKeyDown = (event: KeyboardEvent): boolean => {
    if (event.key !== 'Backspace' || this.select?.searchTerm) return true
    const visible =
      this.value?.filter((id) => !this.isImplied(id) && !this.isHidden(id)) ??
      []
    if (visible.length === (this.value?.length ?? 0)) return true
    if (visible.length) this.removeTag(visible.at(-1))
    return false
  }

  /**
   * Changes from ng-select itself (e.g. clear all) never drop hidden tags,
   * those are only removed via their own badge.
   */
  onModelChange(newValue: number[]) {
    const kept = this.hiddenTagIds.filter((id) => !newValue?.includes(id))
    this.value = [...(newValue ?? []), ...kept]
  }

  removeHiddenTags() {
    if (this.disabled) return
    const hidden = new Set(this.hiddenTagIds)
    if (!hidden.size) return
    const modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Remove hidden tags`
    modal.componentInstance.messageBold = $localize`Remove ${hidden.size} tag(s) you don't have access to?`
    modal.componentInstance.message = $localize`You will not be able to add them back.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Remove`
    modal.componentInstance.confirmClicked.pipe(first()).subscribe(() => {
      modal.close()
      this.value = this.value.filter((id) => !hidden.has(id))
      this.onChange(this.value)
    })
  }

  getTag(id: number) {
    if (this.tags) {
      return this.tags.find((tag) => tag.id == id)
    } else {
      return null
    }
  }

  /**
   * Remove a whole badge i.e. the tag plus any ancestors that no other selected
   * tag still needs.
   */
  removeBadge(tagID: number) {
    if (this.disabled) return
    if (!this.showsHierarchy) return this.removeTag(tagID)

    const ancestors = new Set(this.getParentChain(tagID).map((t) => t.id))
    const needed = new Set(
      this.value
        .filter((id) => id !== tagID && !ancestors.has(id))
        .flatMap((id) => this.getParentChain(id).map((t) => t.id))
    )
    this.value = this.value.filter(
      (id) => id !== tagID && (!ancestors.has(id) || needed.has(id))
    )
    this.onChange(this.value)
  }

  removeTag(tagID: number) {
    if (this.disabled) return

    let index = this.value.indexOf(tagID)
    if (index > -1) {
      const tag = this.getTag(tagID)

      // remove tag
      let oldValue = this.value
      oldValue.splice(index, 1)

      // remove children
      if (this.preserveHierarchy) {
        oldValue = this.removeChildren(oldValue, tag)
      }

      this.value = [...oldValue]
      this.onChange(this.value)
    }
  }

  private removeChildren(tagIDs: number[], tag: Tag) {
    if (tag.children?.length) {
      const childIDs = new Set(tag.children.map((child) => child.id))
      tagIDs = tagIDs.filter((id) => !childIDs.has(id))
      for (const child of tag.children) {
        tagIDs = this.removeChildren(tagIDs, child)
      }
    }
    return tagIDs
  }

  public onAdd(tag: Tag) {
    if (this.preserveHierarchy && tag?.parent) {
      // add all parents recursively
      const parent = this.getTag(tag.parent)
      if (parent && !this.value.includes(parent.id)) {
        this.value = [...this.value, parent.id]
        this.onAdd(parent)
        this.onChange(this.value) // re-emit for ng-select
      }
    }
  }

  createTag(name: string = null, add: boolean = false) {
    var modal = this.modalService.open(TagEditDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.dialogMode.set(EditDialogMode.CREATE)
    if (name) modal.componentInstance.object = { name: name }
    else if (this.select.searchTerm)
      modal.componentInstance.object = { name: this.select.searchTerm }
    this.select.filter(null)
    this.select.detectChanges()
    return firstValueFrom(
      (modal.componentInstance as TagEditDialogComponent).succeeded.pipe(
        first(),
        tap((newTag) => {
          this.tagService.listAll().subscribe((tags) => {
            this.tags = tags.results
            add && this.addTag(newTag.id)
          })
        })
      )
    )
  }

  getSuggestions() {
    if (this.suggestions && this.tags) {
      return this.suggestions
        .filter((id) => !this.value.includes(id))
        .map((id) => this.tags.find((tag) => tag.id == id))
    } else {
      return []
    }
  }

  addTag(id) {
    this.value = [...this.value, id]
    this.onAdd(this.getTag(id))
    this.onChange(this.value)
  }

  get hasPrivate(): boolean {
    return this.value.some(
      (t) => this.tags?.find((t2) => t2.id === t) === undefined
    )
  }

  onFilterDocuments() {
    this.filterDocuments.emit(
      this.tags.filter((t) => this.value.includes(t.id))
    )
  }

  getParentChain(id: number): Tag[] {
    return getTagAncestors(id, this.tagsById)
  }

  private tagsByIdSource: Tag[]
  private tagsByIdCache: Map<number, Tag>

  private get tagsById(): Map<number, Tag> {
    if (this.tagsByIdSource !== this.tags) {
      this.tagsByIdSource = this.tags
      this.tagsByIdCache = new Map(this.tags?.map((t) => [t.id, t]))
    }
    return this.tagsByIdCache
  }
}
