import { TestBed } from '@angular/core/testing';

import { SavedViewConfigService } from './saved-view-config.service';

describe('SavedViewConfigService', () => {
  let service: SavedViewConfigService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(SavedViewConfigService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
