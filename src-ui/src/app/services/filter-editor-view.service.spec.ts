import { TestBed } from '@angular/core/testing';

import { FilterEditorViewService } from './filter-editor-view.service';

describe('FilterEditorViewService', () => {
  let service: FilterEditorViewService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(FilterEditorViewService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
