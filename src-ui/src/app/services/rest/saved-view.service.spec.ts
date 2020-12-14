import { TestBed } from '@angular/core/testing';

import { SavedViewService } from './saved-view.service';

describe('SavedViewService', () => {
  let service: SavedViewService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(SavedViewService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
