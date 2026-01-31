import {
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
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import {
  catchError,
  debounceTime,
  distinctUntilChanged,
  first,
  firstValueFrom,
  of,
  Subject,
  switchMap,
  tap,
} from 'rxjs'
import { Tag } from 'src/app/data/tag'
import { TagService } from 'src/app/services/rest/tag.service'
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
    NgxBootstrapIconsModule,
  ],
})
export class TagsComponent implements OnInit, ControlValueAccessor {
  private tagService = inject(TagService)
  private modalService = inject(NgbModal)

  constructor() {
    this.createTagRef = this.createTag.bind(this)
  }

  onChange = (newValue: number[]) => {}

  onTouched = () => {}

  writeValue(newValue: number[]): void {
    this.value = newValue
    // Ensure selected tags are loaded so they display correctly
    if (this.value && this.value.length > 0) {
      this.tagService.getFew(this.value).subscribe((result) => {
        // Merge these into the existing tags list if they aren't there
        const newTags = result.results.filter(
          (t) => !this.tags.some((existing) => existing.id === t.id)
        )
        if (newTags.length > 0) {
          this.tags = [...this.tags, ...newTags]
        }
      })
    }
  }
  registerOnChange(fn: any): void {
    this.onChange = fn
  }
  registerOnTouched(fn: any): void {
    this.onTouched = fn
  }
  setDisabledState?(isDisabled: boolean): void {
    this.disabled = isDisabled
  }

  tagInput$ = new Subject<string>()
  tagsLoading = false

  ngOnInit(): void {
    this.loadTags()
  }

  loadTags() {
    this.tagInput$
      .pipe(
        debounceTime(200),
        distinctUntilChanged(),
        tap(() => (this.tagsLoading = true)),
        switchMap((term) => {
          return this.tagService.listFiltered(1, 50, 'name', false, term).pipe(
            catchError(() => of({ results: [] })),
            tap(() => (this.tagsLoading = false))
          )
        })
      )
      .subscribe((result) => {
        this.tags = result.results
        // If we have selected values, ensure they aren't lost from the dropdown list visuals
        // (Though ng-select usually handles this if we provide the object, here we only have IDs in this.value)
        // For now, we rely on writeValue's getFew to populate the initial selection.
      })

    // Trigger initial load
    this.tagInput$.next('')
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

  @Output()
  filterDocuments = new EventEmitter<Tag[]>()

  @ViewChild('tagSelect') select: NgSelectComponent

  value: number[] = []

  tags: Tag[] = []

  public createTagRef: (name) => void

  getTag(id: number) {
    if (this.tags) {
      return this.tags.find((tag) => tag.id == id)
    } else {
      return null
    }
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
      oldValue = this.removeChildren(oldValue, tag)

      this.value = [...oldValue]
      this.onChange(this.value)
    }
  }

  private removeChildren(tagIDs: number[], tag: Tag) {
    if (tag.children?.length) {
      const childIDs = tag.children.map((child) => child.id)
      tagIDs = tagIDs.filter((id) => !childIDs.includes(id))
      for (const child of tag.children) {
        tagIDs = this.removeChildren(tagIDs, child)
      }
    }
    return tagIDs
  }

  public onAdd(tag: Tag) {
    if (tag.parent) {
      // add all parents recursively
      const parent = this.getTag(tag.parent)
      this.value = [...this.value, parent.id]
      this.onAdd(parent)
    }
  }

  createTag(name: string = null, add: boolean = false) {
    var modal = this.modalService.open(TagEditDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.dialogMode = EditDialogMode.CREATE
    if (name) modal.componentInstance.object = { name: name }
    else if (this.select.searchTerm)
      modal.componentInstance.object = { name: this.select.searchTerm }
    this.select.filter(null)
    this.select.detectChanges()
    return firstValueFrom(
      (modal.componentInstance as TagEditDialogComponent).succeeded.pipe(
        first(),
        tap((newTag) => {
          // On create, we just add the new tag to our local list so it can be selected
          this.tags = [...this.tags, newTag]
          add && this.addTag(newTag.id)
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
    // Returns ancestors from root → immediate parent for a tag id
    const chain: Tag[] = []
    let current = this.getTag(id)
    const guard = new Set<number>()
    while (current?.parent) {
      if (guard.has(current.parent)) break
      guard.add(current.parent)
      const parent = this.getTag(current.parent)
      if (!parent) break
      chain.unshift(parent)
      current = parent
    }
    return chain
  }
}
