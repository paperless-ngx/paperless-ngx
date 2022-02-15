import { Component, forwardRef, Input, OnInit } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { TagEditDialogComponent } from 'src/app/components/manage/tag-list/tag-edit-dialog/tag-edit-dialog.component';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { TagService } from 'src/app/services/rest/tag.service';

@Component({
  providers: [{
    provide: NG_VALUE_ACCESSOR,
    useExisting: forwardRef(() => TagsComponent),
    multi: true
  }],
  selector: 'app-input-tags',
  templateUrl: './tags.component.html',
  styleUrls: ['./tags.component.scss']
})
export class TagsComponent implements OnInit, ControlValueAccessor {

  constructor(private tagService: TagService, private modalService: NgbModal) {
    this.createTagRef = this.createTag.bind(this)
  }

  onChange = (newValue: number[]) => {};

  onTouched = () => {};

  writeValue(newValue: number[]): void {
    this.value = newValue
  }
  registerOnChange(fn: any): void {
    this.onChange = fn;
  }
  registerOnTouched(fn: any): void {
    this.onTouched = fn;
  }
  setDisabledState?(isDisabled: boolean): void {
    this.disabled = isDisabled;
  }

  ngOnInit(): void {
    this.tagService.listAll().subscribe(result => {
      this.tags = result.results
    })
  }

  @Input()
  disabled = false

  @Input()
  hint

  @Input()
  suggestions: number[]

  value: number[]

  tags: PaperlessTag[]

  public createTagRef: (name) => void

  private _lastSearchTerm: string

  getTag(id) {
    if (this.tags) {
      return this.tags.find(tag => tag.id == id)
    } else {
      return null
    }
  }

  removeTag(id) {
    let index = this.value.indexOf(id)
    if (index > -1) {
      let oldValue = this.value
      oldValue.splice(index, 1)
      this.value = [...oldValue]
      this.onChange(this.value)
    }
  }

  createTag(name: string = null) {
    var modal = this.modalService.open(TagEditDialogComponent, {backdrop: 'static'})
    modal.componentInstance.dialogMode = 'create'
    if (name) modal.componentInstance.object = { name: name }
    else if (this._lastSearchTerm) modal.componentInstance.object = { name: this._lastSearchTerm }
    modal.componentInstance.success.subscribe(newTag => {
      this.tagService.listAll().subscribe(tags => {
        this.tags = tags.results
        this.value = [...this.value, newTag.id]
        this.onChange(this.value)
      })
    })
  }

  getSuggestions() {
    if (this.suggestions && this.tags) {
      return this.suggestions.filter(id => !this.value.includes(id)).map(id => this.tags.find(tag => tag.id == id))
    } else {
      return []
    }
  }

  addTag(id) {
    this.value = [...this.value, id]
    this.onChange(this.value)
  }

  clearLastSearchTerm() {
    this._lastSearchTerm = null
  }

  onSearch($event) {
    this._lastSearchTerm = $event.term
  }

  onBlur() {
    setTimeout(() => {
      this.clearLastSearchTerm()
    }, 3000);
  }

}
