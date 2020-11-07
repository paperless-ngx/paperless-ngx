import { TestBed } from '@angular/core/testing';

import { ConsumerStatusService } from './consumer-status.service';

describe('ConsumerStatusService', () => {
  let service: ConsumerStatusService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(ConsumerStatusService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
