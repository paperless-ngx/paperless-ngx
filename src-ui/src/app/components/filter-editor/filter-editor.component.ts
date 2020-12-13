import { Component, EventEmitter, Input, Output, ElementRef, AfterViewInit, QueryList, ViewChild, ViewChildren } from '@angular/core';
import { AbstractPaperlessService } from 'src/app/services/rest/abstract-paperless-service';
import { ObjectWithId } from 'src/app/data/object-with-id';
import { FilterEditorViewService } from 'src/app/services/filter-editor-view.service'
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { FilterDropdownComponent } from './filter-dropdown/filter-dropdown.component'
import { FilterDropdownDateComponent } from './filter-dropdown-date/filter-dropdown-date.component'
import { fromEvent } from 'rxjs';
import { debounceTime, distinctUntilChanged, tap } from 'rxjs/operators';
import { NgbDateStruct } from '@ng-bootstrap/ng-bootstrap';

@Component({
  selector: 'app-filter-editor',
  templateUrl: './filter-editor.component.html',
  styleUrls: ['./filter-editor.component.scss']
})
export class FilterEditorComponent implements AfterViewInit {

  constructor() { }

  @Input()
  filterEditorService: FilterEditorViewService

  @Output()
  clear = new EventEmitter()

  @Output()
  apply = new EventEmitter()

  @ViewChild('filterTextInput') filterTextInput: ElementRef;

  ngAfterViewInit() {
    fromEvent(this.filterTextInput.nativeElement,'keyup').pipe(
      debounceTime(150),
      distinctUntilChanged(),
      tap()
    ).subscribe((event: Event) => {
      this.filterEditorService.filterText = (event.target as HTMLInputElement).value
      this.applyFilters()
    })
  }

  applyFilters() {
    this.apply.next()
  }

  clearSelected() {
    this.filterEditorService.clear()
    this.clear.next()
  }

  onToggleTag(tag: PaperlessTag) {
    this.filterEditorService.toggleFitlerByTag(tag)
    this.applyFilters()
  }

  onToggleCorrespondent(correspondent: PaperlessCorrespondent) {
    this.filterEditorService.toggleFitlerByCorrespondent(correspondent)
    this.applyFilters()
  }

  onToggleDocumentType(documentType: PaperlessDocumentType) {
    this.filterEditorService.toggleFitlerByDocumentType(documentType)
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
