import { Component, EventEmitter, Input, Output, OnInit, OnDestroy } from '@angular/core';
import { FilterEditorViewService } from 'src/app/services/filter-editor-view.service'
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { Subject, Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import { NgbDateStruct } from '@ng-bootstrap/ng-bootstrap';

@Component({
  selector: 'app-filter-editor',
  templateUrl: './filter-editor.component.html',
  styleUrls: ['./filter-editor.component.scss']
})
export class FilterEditorComponent implements OnInit, OnDestroy {

  constructor() { }

  @Input()
  filterEditorService: FilterEditorViewService

  @Output()
  clear = new EventEmitter()

  @Output()
  apply = new EventEmitter()

  get filterText() {
    return this.filterEditorService.filterText
  }

  set filterText(value) {
    this.filterTextDebounce.next(value)
  }

  filterTextDebounce: Subject<string>
  subscription: Subscription

  ngOnInit() {
    this.filterTextDebounce = new Subject<string>()
    this.subscription = this.filterTextDebounce.pipe(
      debounceTime(400),
      distinctUntilChanged()
    ).subscribe(title => {
      this.filterEditorService.filterText = title
      this.applyFilters()
    })
  }

  ngOnDestroy() {
    this.subscription.unsubscribe()
  }

  applyFilters() {
    this.apply.next()
  }

  clearSelected() {
    this.filterEditorService.clear()
    this.clear.next()
  }

  onToggleTag(tag: PaperlessTag) {
    this.filterEditorService.toggleFilterByTag(tag)
    this.applyFilters()
  }

  onToggleCorrespondent(correspondent: PaperlessCorrespondent) {
    this.filterEditorService.toggleFilterByCorrespondent(correspondent)
    this.applyFilters()
  }

  onToggleDocumentType(documentType: PaperlessDocumentType) {
    this.filterEditorService.toggleFilterByDocumentType(documentType)
    this.applyFilters()
  }

  onDateCreatedBeforeSet(date: NgbDateStruct) {
    this.filterEditorService.setDateCreatedBefore(date)
    this.applyFilters()
  }

  onDateCreatedAfterSet(date: NgbDateStruct) {
    this.filterEditorService.setDateCreatedAfter(date)
    this.applyFilters()
  }

  onDateAddedBeforeSet(date: NgbDateStruct) {
    this.filterEditorService.setDateAddedBefore(date)
    this.applyFilters()
  }

  onDateAddedAfterSet(date: NgbDateStruct) {
    this.filterEditorService.setDateAddedAfter(date)
    this.applyFilters()
  }
}
