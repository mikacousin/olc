import pytest

from core.universe import (
    ArtNetSettings,
    Protocol,
    SacnSettings,
    UniverseConfig,
    UniverseMap,
)


class TestArtNetSettings:
    """Test ArtNetSettings configuration"""

    def test_default_init(self) -> None:
        """Test default parameters"""
        settings = ArtNetSettings()
        assert settings.net == 0
        assert settings.sub == 0

    def test_valid_init(self) -> None:
        """Test valid configuration"""
        settings = ArtNetSettings(net=127, sub=15)
        assert settings.net == 127
        assert settings.sub == 15

    def test_invalid_net(self) -> None:
        """Test invalid net parameters"""
        with pytest.raises(ValueError, match="ArtNet net must be 0-127"):
            ArtNetSettings(net=-1)
        with pytest.raises(ValueError, match="ArtNet net must be 0-127"):
            ArtNetSettings(net=128)

    def test_invalid_sub(self) -> None:
        """Test invalid sub parameters"""
        with pytest.raises(ValueError, match="ArtNet sub must be 0-15"):
            ArtNetSettings(sub=-1)
        with pytest.raises(ValueError, match="ArtNet sub must be 0-15"):
            ArtNetSettings(sub=16)


class TestSacnSettings:
    """Test sACN configuration"""

    def test_default_init(self) -> None:
        """Test default parameters"""
        settings = SacnSettings()
        assert settings.priority == 100

    def test_valid_init(self) -> None:
        """Test valid configuration"""
        settings = SacnSettings(priority=1)
        assert settings.priority == 1
        settings = SacnSettings(priority=200)
        assert settings.priority == 200

    def test_invalid_priority(self) -> None:
        """Test invalid priority"""
        with pytest.raises(ValueError, match="sACN priority must be 1-200"):
            SacnSettings(priority=0)
        with pytest.raises(ValueError, match="sACN priority must be 1-200"):
            SacnSettings(priority=201)


class TestUniverseConfig:
    """Test UniverseConfig class"""

    def test_valid_init(self) -> None:
        """Test valid initialization"""
        config = UniverseConfig(0)
        assert config.universe_id == 0
        assert config.protocols == set()
        assert isinstance(config.artnet, ArtNetSettings)
        assert isinstance(config.sacn, SacnSettings)

    def test_invalid_init(self) -> None:
        """Test invalid initialization"""
        err_msg = "universe_id must be a non-negative integer"
        with pytest.raises(ValueError, match=err_msg):
            UniverseConfig(-1)
        with pytest.raises(ValueError, match=err_msg):
            UniverseConfig("1")  # type: ignore

    def test_enable_disable_protocols(self) -> None:
        """Test enabling and disabling protocols"""
        config = UniverseConfig(1)
        config.enable(Protocol.ARNET, Protocol.SACN)
        assert config.protocols == {Protocol.ARNET, Protocol.SACN}

        config.disable(Protocol.ARNET)
        assert config.protocols == {Protocol.SACN}

    def test_set_protocols(self) -> None:
        """Test replacing protocol sets"""
        config = UniverseConfig(1)
        config.set_protocols({Protocol.ARNET})
        assert config.protocols == {Protocol.ARNET}

        config.set_protocols({Protocol.SACN})
        assert config.protocols == {Protocol.SACN}

    def test_disable_all(self) -> None:
        """Test disabling all protocols"""
        config = UniverseConfig(1)
        config.enable(Protocol.ARNET, Protocol.SACN)
        config.disable_all()
        assert config.protocols == set()

    def test_universe_0_forbidden_sacn(self) -> None:
        """Test protocol restrictions on universe 0"""
        config = UniverseConfig(0)
        err_msg = "Protocol.SACN is not allowed on universe 0"
        with pytest.raises(ValueError, match=err_msg):
            config.enable(Protocol.SACN)

        with pytest.raises(ValueError, match=err_msg):
            config.set_protocols({Protocol.SACN})

        # ArtNet should be fine on universe 0
        config.enable(Protocol.ARNET)
        assert config.protocols == {Protocol.ARNET}


class TestUniverseMap:
    """Test UniverseMap logic"""

    def test_init_valid(self) -> None:
        """Test valid initialization"""
        umap = UniverseMap(num_universes=10)
        assert len(umap) == 10
        assert 0 in umap
        assert 9 in umap

    def test_init_invalid(self) -> None:
        """Test invalid initialization"""
        with pytest.raises(ValueError, match="num_universe must be at least 1"):
            UniverseMap(num_universes=0)

    def test_delegated_methods(self) -> None:
        """Test delegated methods from map to universes"""
        umap = UniverseMap(num_universes=2)

        # Test enable_protocol
        umap.enable_protocol(1, Protocol.SACN)
        assert umap[1].protocols == {Protocol.SACN}

        # Test set_protocols
        umap.set_protocols(1, {Protocol.ARNET})
        assert umap[1].protocols == {Protocol.ARNET}

        # Test disable_protocol
        umap.disable_protocol(1, Protocol.ARNET)
        assert umap[1].protocols == set()

        # Test disable_universe
        umap.enable_protocol(0, Protocol.ARNET)
        umap.disable_universe(0)
        assert umap[0].protocols == set()

    def test_out_of_bounds_access(self) -> None:
        """Test accessing a non-existent universe"""
        umap = UniverseMap(num_universes=5)
        err_msg = r"Universe 999 does not exist \(valid range: 0-4\)"
        with pytest.raises(KeyError, match=err_msg):
            _ = umap[999]

    def test_iteration(self) -> None:
        """Test iteration over universe map"""
        umap = UniverseMap(num_universes=3)
        configs = list(umap)
        assert len(configs) == 3
        assert configs[0].universe_id == 0
        assert configs[1].universe_id == 1
        assert configs[2].universe_id == 2
