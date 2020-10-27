import { TestBed } from '@angular/core/testing';

import { DocumentListViewService } from './document-list-view.service';

describe('DocumentListViewService', () => {
  let service: DocumentListViewService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(DocumentListViewService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
