import numpy as np


def create_resource_grid(time_slots=10, frequency_units=20):
    """
    Create an abstract time-frequency resource grid.

    Values:
        0 = unused
        1 = eMBB
        2 = URLLC
    """
    grid = np.zeros((time_slots, frequency_units), dtype=int)

    # Initially allocate the entire grid to eMBB.
    grid[:, :] = 1

    return grid


def mark_urllc_resources(grid, resources):
    """
    Mark selected resource positions as URLLC.

    resources:
        List of (time_index, frequency_index) tuples.
    """
    for t, f in resources:
        grid[t, f] = 2

    return grid


if __name__ == "__main__":
    grid = create_resource_grid()

    print("Initial eMBB grid:")
    print(grid)

    # Example URLLC allocation
    urllc_resources = [
        (2, 5),
        (2, 6),
        (3, 5),
        (3, 6)
    ]

    grid = mark_urllc_resources(grid, urllc_resources)

    print("\nAfter URLLC allocation:")
    print(grid)