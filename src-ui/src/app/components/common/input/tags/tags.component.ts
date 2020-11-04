import { ThrowStmt } from '@angular/compiler';
import { Component, forwardRef, Input, OnInit } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { Observable } from 'rxjs';
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
  styleUrls: ['./tags.component.css']
})
export class TagsComponent implements OnInit, ControlValueAccessor {

  constructor(private tagService: TagService, private modalService: NgbModal) { }


  onChange = (newValue: number[]) => {};
  
  onTouched = () => {};

  writeValue(newValue: number[]): void {
    this.value = newValue
    if (this.tags) {
      this.displayValue = newValue
    }
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
      this.displayValue = this.value
    })
  }

  @Input()
  disabled = false

  @Input()
  hint

  value: number[]

  displayValue: number[] = []

  tags: PaperlessTag[]

  getTag(id) {
    return this.tags.find(tag => tag.id == id)
  }

  removeTag(id) {
    let index = this.displayValue.indexOf(id)
    if (index > -1) {
      this.displayValue.splice(index, 1)
      this.onChange(this.displayValue)
    }
  }

  addTag(id) {
    let index = this.displayValue.indexOf(id)
    if (index == -1) {
      this.displayValue.push(id)
      this.onChange(this.displayValue)
    }
  }


  createTag() {
    var modal = this.modalService.open(TagEditDialogComponent, {backdrop: 'static'})
    modal.componentInstance.dialogMode = 'create'
    modal.componentInstance.success.subscribe(newTag => {
      this.tagService.list().subscribe(tags => {
        this.tags = tags.results
        this.addTag(newTag.id)
      })
    })
  }

}
